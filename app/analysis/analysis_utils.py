from app import db
from app.models import Task
from app.main import controller
from config import Config
from flask import current_app
import asyncio
import numpy as np
import pandas as pd
import requests
from math import sqrt, isnan
import random


async def async_analysis(tasks):
    """ Generate asyncio tasks and run them, returning when all tasks are done"""

    # generates coroutines out of task obects
    async_tasks = [UTILITY_MAP[task.task_parameters.get('utility')](task) for task in tasks]

    # here tasks are actually executed asynchronously
    # returns list of results *or* exceptions if a task fail
    results = await asyncio.gather(*async_tasks, return_exceptions=True)
    current_app.logger.info("Tasks finished, returning results")
    return results


class AnalysisUtility(object):
    def __init__(self):
        self.utility_name = None
        self.utility_description = None
        self.utility_parameters = None
        self.input_type = None
        self.output_type = None

    async def __call__(self, task):
        return {
            'error': 'This utility has not yet been implemented'
        }

    # TODO: Now the toolchain generation simply searches backwards from the final tool, this needs to be improved to a
    #       proper graph search in the future
    async def get_input_task(self, task):
        input_task_uuid = task.task_parameters.get('target_uuid')
        if input_task_uuid:
            input_task = Task.query.filter_by(uuid=input_task_uuid).first()
            if input_task is None:
                raise ValueError('Invalid target_uuid')
        else:
            search_parameters = task.task_parameters.get('target_search')
            if search_parameters is None:
                return None
            source_utilities = [key for key, value in UTILITY_MAP.items() if key != self.utility_name
                                and value.output_type == self.input_type]
            if not source_utilities:
                input_task = await controller.execute_async_tasks(user=task.user, queries=('search', search_parameters))
            else:
                # Copy the task parameters from the originating task, replacing the utility parameter with the
                # correct value
                task_parameters = task.task_parameters.copy()
                task_parameters['utility'] = source_utilities[0]
                input_task = await controller.execute_async_tasks(user=task.user, queries=('analysis', task_parameters),
                                                                  parent_id=task.hist_parent_id)
        return input_task

    def get_description(self):
        return {
            'utility_name': self.utility_name,
            'utility_description': self.utility_description,
            'utility_parameters': self.utility_parameters,
            'input_type': self.input_type,
            'output_type': self.output_type
        }


class ExtractFacets(AnalysisUtility):
    def __init__(self):
        super(ExtractFacets, self).__init__()
        self.utility_name = 'extract_facets'
        self.utility_description = 'Examines the document set given as input, and finds all the different facets for which values have been set in at least some of the documents.'
        self.utility_parameters = []
        self.input_type = 'search_result'
        self.output_type = 'facet_list'

    async def __call__(self, task):
        """ Extract all facet values found in the input data and the number of occurrences for each."""
        input_task = await self.get_input_task(task)
        task.hist_parent_id = input_task.uuid
        db.session.commit()
        input_data = input_task.task_result.result
        facets = {}
        for feature in input_data[Config.FACETS_KEY]:
            if Config.DATABASE_IN_USE == 'demo':
                if feature['type'] != 'facet':
                    continue
                values = {}
                for item in feature[Config.FACET_ATTRIBUTES_KEY][Config.FACET_ITEMS_KEY]:
                    values[item[Config.FACET_ATTRIBUTES_KEY][Config.FACET_VALUE_LABEL_KEY]] = \
                        item[Config.FACET_ATTRIBUTES_KEY][Config.FACET_VALUE_HITS_KEY]
                facets[feature[Config.FACET_ID_KEY]] = values
            elif Config.DATABASE_IN_USE == 'newseye':
                values = {}
                for item in feature[Config.FACET_ITEMS_KEY]:
                    values[item[Config.FACET_VALUE_LABEL_KEY]] = item[Config.FACET_VALUE_HITS_KEY]
                facets[feature[Config.FACET_ID_KEY]] = values
        return facets


class CommonFacetValues(AnalysisUtility):
    def __init__(self):
        super(CommonFacetValues, self).__init__()
        self.utility_name = 'common_facet_values'
        self.utility_description = 'Sorts the facet values for facet_name by decreasing number of matching documents and returns the n most common facet values and their document counts'
        self.utility_parameters = [
            {
                'parameter_name': 'n',
                'parameter_description': 'The number of facet values to be included in the result',
                'parameter_type': 'integer',
                'parameter_default': 5,
                'parameter_is_required': False,
            },
            {
                'parameter_name': 'facet_name',
                'parameter_description': 'The name of the facet to be analysed, e.g. PUB_YEAR',
                'parameter_type': 'string',
                'parameter_default': None,
                'parameter_is_required': True
            }
        ]
        self.input_type = 'facet_list'
        self.output_type = 'topic_list'

    async def __call__(self, task):
        default_parameters = {
            'n': 5,
            'facet_name': 'TOPIC',
        }
        n = int(task.task_parameters.get('n', default_parameters['n']))
        facet_name = task.task_parameters.get('facet_name', default_parameters['facet_name'])
        facet_name = Config.AVAILABLE_FACETS.get(facet_name, facet_name)

        input_task = await self.get_input_task(task)
        task.hist_parent_id = input_task.uuid
        db.session.commit()

        input_data = input_task.task_result.result
        facets = input_data[facet_name]
        facet_list = [(facets[key], key) for key in facets.keys()]
        facet_list.sort(reverse=True)
        facet_list = facet_list[:n]
        facet_list = [{"facet_value": key, "document_count": value} for value, key in facet_list]
        interestingness = [1] * len(facet_list)
        return {'facet_counts': facet_list, 'interestingness': interestingness}


class GenerateTimeSeries(AnalysisUtility):
    def __init__(self):
        super(GenerateTimeSeries, self).__init__()
        self.utility_name = 'generate_time_series'
        self.utility_description = ''
        self.utility_parameters = [
            {
                'parameter_name': 'facet_name',
                'parameter_description': 'Not yet written',
                'parameter_type': 'string',
                'parameter_default': None,
                'parameter_is_required': True
            }
        ]
        self.input_type = 'time_split_query'
        self.output_type = 'time_series'

    async def __call__(self, task):
        # TODO: Add parameter for imputting zeroes?
        facet_name = task.task_parameters.get('facet_name')
        facet_string = Config.AVAILABLE_FACETS.get(facet_name)
        if facet_string is None:
            raise TypeError("Facet not specified or specified facet not available in current database")

        input_task = await self.get_input_task(task)
        task.hist_parent_id = input_task.uuid
        db.session.commit()
        if input_task is None or input_task.task_status != 'finished':
            raise TypeError("No task results available for analysis")

        input_data = input_task.task_result.result
        subquery_tasks = Task.query.filter(Task.uuid.in_(input_data)).all()
        f_counts = []
        for task in subquery_tasks:
            if task.task_result is None:
                current_app.logger.error('Empty task result in input for task_analysis')
                continue
            task_result = task.task_result.result
            year = task.task_parameters['f[{}][]'.format(Config.AVAILABLE_FACETS['PUB_YEAR'])]
            total_hits = task_result['meta']['pages']['total_count']
            for item in task_result[Config.FACETS_KEY]:
                if item['id'] == facet_string and item['type'] == 'facet':
                    f_counts.extend([[year, facet['attributes']['value'], facet['attributes']['hits'],
                                      facet['attributes']['hits'] / total_hits] for facet in
                                     item['attributes']['items']])
                    break
            # TODO: count the number of items with no value defined for the desired facet
        df = pd.DataFrame(f_counts, columns=['year', facet_name, 'count', 'rel_count'])
        abs_counts = df.pivot(index=facet_name, columns='year', values='count').fillna(0)
        rel_counts = df.pivot(index=facet_name, columns='year', values='rel_count').fillna(0)
        analysis_results = {
            'absolute_counts': abs_counts.to_dict(orient='index'),
            'relative_counts': rel_counts.to_dict(orient='index')
        }
        return analysis_results


class SplitDocumentSetByFacet(AnalysisUtility):
    def __init__(self):
        super(SplitDocumentSetByFacet, self).__init__()
        self.utility_name = 'split_document_set_by_facet'
        self.utility_description = ''
        self.utility_parameters = [
            {
                'parameter_name': 'facet_name',
                'parameter_description': 'Not yet written',
                'parameter_type': 'string',
                'parameter_default': None,
                'parameter_is_required': True
            }
        ]
        self.input_type = 'search'
        self.output_type = 'time_split_query'

    async def __call__(self, task):
        default_parameters = {
            'split_facet': 'PUB_YEAR'
        }
        input_task = await self.get_input_task(task)
        input_data = input_task.task_result.result
        split_facet = task.task_parameters.get('split_facet', default_parameters['split_facet'])
        for item in input_data[Config.FACETS_KEY]:
            if item['id'] == Config.AVAILABLE_FACETS[split_facet] and item['type'] == 'facet':
                facet_totals = [(facet['attributes']['value'], facet['attributes']['hits']) for facet in
                                item['attributes']['items']]
                break
        else:
            raise TypeError(
                "Search results don't contain required facet {}".format(Config.AVAILABLE_FACETS[split_facet]))
        facet_totals.sort()
        original_search = input_task.task_parameters
        queries = [{'f[{}][]'.format(Config.AVAILABLE_FACETS[split_facet]): item[0]} for item in facet_totals]
        for query in queries:
            query.update(original_search)
        queries = [('search', query) for query in queries]
        task_ids = await controller.execute_async_tasks(user=task.user, queries=queries, return_tasks=False,
                                                        parent_id=input_task.uuid)
        return [str(task_id) for task_id in task_ids]


class FindStepsFromTimeSeries(AnalysisUtility):
    def __init__(self):
        super(FindStepsFromTimeSeries, self).__init__()
        self.utility_name = 'find_steps_from_time_series'
        self.utility_description = ''
        self.utility_parameters = [
            {
                'parameter_name': 'step_threshold',
                'parameter_description': 'Not yet written',
                'parameter_type': 'float',
                'parameter_default': None,
                'parameter_is_required': False
            },
            {
                'parameter_name': 'column_name',
                'parameter_description': 'Not yet written',
                'parameter_type': 'string',
                'parameter_default': None,
                'parameter_is_required': False
            }
        ]
        self.input_type = 'time_series'
        self.output_type = 'step_list'

    async def __call__(self, task, use_data=False):
        if not use_data:
            column_name = task.task_parameters.get('column_name')
            step_threshold = task.task_parameters.get('step_threshold')

            # looks for tasks to be done before this one
            # TODO: avoid it, will be done by Planner
            input_task = await self.get_input_task(task)
            task.hist_parent_id = input_task.uuid
            db.session.commit()
            if input_task is None or input_task.task_status != 'finished':
                raise TypeError("No task results available for analysis")
            input_data = input_task.task_result.result

            input_data = pd.DataFrame(input_data['relative_counts'])
            input_data.index = pd.to_numeric(input_data.index)
            index_start = input_data.index.min()
            index_end = input_data.index.max()
            idx = np.arange(index_start, index_end + 1)
            input_data = input_data.reindex(idx, fill_value=0)
        else:
            input_data = task
            step_threshold = None
        steps = {}
        if column_name:
            columns = [column_name]
        else:
            columns = input_data.columns
        for column in columns:
            data = input_data[column]
            prod, _ = self.mz_fwt(data, 3)
            step_indices = self.find_steps(prod, step_threshold)
            step_sizes, errors = self.get_step_sizes(input_data[column], step_indices)
            step_times = [int(input_data.index[idx]) for idx in step_indices]
            steps[column] = list(zip(step_times, step_sizes, errors))
        # TODO: Fix output to match documentation
        # TODO: Implement interestingness values
        return steps

    def mz_fwt(self, x, n=3):
        """
        A modified version of the code at https://github.com/thomasbkahn/step-detect:

        Computes the multiscale product of the Mallat-Zhong discrete forward
        wavelet transform up to and including scale n for the input data x.
        If n is even, the spikes in the signal will be positive. If n is odd
        the spikes will match the polarity of the step (positive for steps
        up, negative for steps down).
        This function is essentially a direct translation of the MATLAB code
        provided by Sadler and Swami in section A.4 of the following:
        http://www.dtic.mil/dtic/tr/fulltext/u2/a351960.pdf
        Parameters
        ----------
        x : numpy array
            1 dimensional array that represents time series of data points
        n : int
            Highest scale to multiply to
        Returns
        -------
        prod : numpy array
            The multiscale product for x
        """
        n_pnts = x.size
        lambda_j = [1.5, 1.12, 1.03, 1.01][0:n]
        if n > 4:
            lambda_j += [1.0] * (n - 4)

        h = np.array([0.125, 0.375, 0.375, 0.125])
        g = np.array([2.0, -2.0])

        gn = [2]
        hn = [3]
        for j in range(1, n):
            q = 2 ** (j - 1)
            gn.append(q + 1)
            hn.append(3 * q + 1)

        s = x
        prod = np.ones(n_pnts)
        wavelets = np.ones((n, n_pnts))
        for j in range(n):
            s = np.concatenate((s[::-1], s, s[::-1]))
            n_zeros = 2 ** j - 1
            gz = self._insert_zeros(g, n_zeros)
            hz = self._insert_zeros(h, n_zeros)
            current = (1.0 / lambda_j[j]) * np.convolve(s, gz)
            current = current[n_pnts + gn[j] - 1:2 * n_pnts + gn[j] - 1]
            prod *= current
            wavelets[j] *= current
            s_new = np.convolve(s, hz)
            s = s_new[n_pnts + hn[j] - 1:2 * n_pnts + hn[j] - 1]
        prod /= np.abs(prod).max()
        return prod, wavelets

    @staticmethod
    def _insert_zeros(x, n):
        """
        From https://github.com/thomasbkahn/step-detect.

        Helper function for mz_fwt. Splits input array and adds n zeros
        between values.
        """
        newlen = (n + 1) * x.size
        out = np.zeros(newlen)
        indices = list(range(0, newlen - n, n + 1))
        out[indices] = x
        return out

    @staticmethod
    def find_steps(array, threshold=None):
        """
        A modified version of the code at https://github.com/thomasbkahn/step-detect.

        Finds local maxima by segmenting array based on positions at which
        the threshold value is crossed. Note that this thresholding is
        applied after the absolute value of the array is taken. Thus,
        the distinction between upward and downward steps is lost. However,
        get_step_sizes can be used to determine directionality after the
        fact.
        Parameters
        ----------
        array : numpy array
            1 dimensional array that represents time series of data points
        threshold : int / float
            Threshold value that defines a step. If no threshold value is specified, it is set to 2 standard deviations
        Returns
        -------
        steps : list
            List of indices of the detected steps
        """
        if threshold is None:
            threshold = 4 * np.var(array)  # Use 2 standard deviations as the threshold
        steps = []
        above_points = np.where(array > threshold, 1, 0)
        below_points = np.where(array < -threshold, 1, 0)
        ap_dif = np.diff(above_points)
        bp_dif = np.diff(below_points)
        pos_cross_ups = np.where(ap_dif == 1)[0]
        pos_cross_dns = np.where(ap_dif == -1)[0]
        neg_cross_dns = np.where(bp_dif == 1)[0]
        neg_cross_ups = np.where(bp_dif == -1)[0]
        # If cross_dns is longer that cross_ups, the first entry in cross_dns is zero, which will cause a crash
        if len(pos_cross_dns) > len(pos_cross_ups):
            pos_cross_dns = pos_cross_dns[1:]
        if len(neg_cross_ups) > len(neg_cross_dns):
            neg_cross_ups = neg_cross_ups[1:]
        for upi, dni in zip(pos_cross_ups, pos_cross_dns):
            steps.append(np.argmax(array[upi: dni]) + upi + 1)
        for dni, upi in zip(neg_cross_dns, neg_cross_ups):
            steps.append(np.argmin(array[dni: upi]) + dni + 1)
        return sorted(steps)

    # TODO: instead of using just the original data, perhaps by odd-symmetric periodical extension??
    #  This should improve the accuracy close to the beginning and end of the signal
    @staticmethod
    def get_step_sizes(array, indices, window=1000):
        """
        A modified version of the code at https://github.com/thomasbkahn/step-detect.

        Calculates step size for each index within the supplied list. Step
        size is determined by averaging over a range of points (specified
        by the window parameter) before and after the index of step
        occurrence. The directionality of the step is reflected by the sign
        of the step size (i.e. a positive value indicates an upward step,
        and a negative value indicates a downward step). The combined
        standard deviation of both measurements (as a measure of uncertainty
        in step calculation) is also provided.
        Parameters
        ----------
        array : numpy array
            1 dimensional array that represents time series of data points
        indices : list
            List of indices of the detected steps (as provided by
            find_steps, for example)
        window : int, optional
            Number of points to average over to determine baseline levels
            before and after step.
        Returns
        -------
        step_sizes : list
            List of tuples describing the mean of the data before and after the detected step
        step_error : list
        """
        step_sizes = []
        step_error = []
        indices = sorted(indices)
        last = len(indices) - 1
        for i, index in enumerate(indices):
            if len(indices) == 1:
                q = min(window, index, len(array) - 1 - index)
            elif i == 0:
                q = min(window, indices[i + 1] - index, index)
            elif i == last:
                q = min(window, index - indices[i - 1], len(array) - 1 - index)
            else:
                q = min(window, index - indices[i - 1], indices[i + 1] - index)
            a = array[index - q: index + 1]
            b = array[index: index + q + 1]
            step_sizes.append((a.mean(), b.mean()))
            error = sqrt(a.var() + b.var())
            if isnan(error):
                step_error.append(abs(step_sizes[-1][1] - step_sizes[-1][0]))
            else:
                step_error.append(error)
        return step_sizes, step_error


# TODO: planner plans the task according to the task dependencies tree
#  Later on this will become an investigator
class Planner(AnalysisUtility):
    def __init__(self):
        super(Planner, self).__init__()
        self.utility_name = None
        self.utility_description = None
        self.utility_parameters = None
        self.input_type = None
        self.output_type = None

    async def __call__(self, task):
        results = []
        while not self.satisfied(results):
            research_plan = self.plan_the_research(task, results)
            results = await async_analysis(research_plan)

        return {
            'error': 'This utility has not yet been implemented'
        }

    @staticmethod
    def satisfied(task, results):
        return True

    @staticmethod
    def plan_the_research(task, results):
        return []  # return a list of new tasks


class CompareDocumentSets(AnalysisUtility):
    async def __call__(self, task):
        input_task = await self.get_input_task(task)
        input_data = input_task.task_result.result


class WordCount(AnalysisUtility):
    async def __call__(self, task):
        input_task = await self.get_input_task(task)
        input_data = input_task.task_result.result
        word_counts = self.do_magic(input_data)
        return word_counts

    @staticmethod
    def do_magic(data):
        return {'Stuff': 1}


class ExtractDocumentIds(AnalysisUtility):
    def __init__(self):
        super(ExtractDocumentIds, self).__init__()
        self.utility_name = 'extract_document_ids'
        self.utility_description = 'Examines the document set given as input, and extracts the document_ids for each of the documents.'
        self.utility_parameters = []
        self.input_type = 'search_result'
        self.output_type = 'id_list'

    async def __call__(self, task):
        demo_documents = int(task.task_parameters.get('demo_mode', None))
        if demo_documents:
            return [random.randint(0, 9458) for i in range(demo_documents)]
        else:
            input_task = await self.get_input_task(task)
            task.hist_parent_id = input_task.uuid
            db.session.commit()
            input_data = input_task.task_result.result
            document_ids = [item['id'] for item in input_data['data']]
            return document_ids


class QueryTopicModel(AnalysisUtility):
    def __init__(self):
        super(QueryTopicModel, self).__init__()
        self.utility_name = 'query_topic_model'
        self.utility_description = 'Queries the selected topic model.'
        self.utility_parameters = [
            {
                'parameter_name': 'model_type',
                'parameter_description': 'The type of the topic model to use',
                'parameter_type': 'string',
                'parameter_default': None,
                'parameter_is_required': True,
            },
            {
                'parameter_name': 'model_name',
                'parameter_description': 'The name of the topic model to use',
                'parameter_type': 'string',
                'parameter_default': None,
                'parameter_is_required': False,
            },
        ]
        self.input_type = 'id_list'
        self.output_type = 'topic_analysis'

    async def __call__(self, task):
        model_type = task.task_parameters.get('model_type')
        if model_type is None:
            raise KeyError
        model_name = task.task_parameters.get('model_name')
        if model_name is None:
            available_models = self.request_topic_models(model_type)
            model_name = available_models[0]['name']
        input_task = await self.get_input_task(task)
        db.session.commit()
        payload = {
            'model': model_name,
            'documents': input_task.task_result.result
        }
        response = requests.post('{}/{}/query'.format(Config.TOPIC_MODEL_URI, model_type), json=payload)
        uuid = response.json().get('task_uuid')
        if not uuid:
            raise ValueError('Invalid response from the Topic Model API')
        delay = 60
        while delay < 300:
            await asyncio.sleep(delay)
            delay *= 1.5
            response = requests.post('{}/query-results'.format(Config.TOPIC_MODEL_URI), json={'task_uuid': uuid})
            if response.status_code == 200:
                break
        return response.json()

    @staticmethod
    def request_topic_models(model_type):
        response = requests.get('{}/{}/list-models'.format(Config.TOPIC_MODEL_URI, model_type))
        return response.json()


UTILITY_MAP = {
    'extract_facets': ExtractFacets(),
    'common_facet_values': CommonFacetValues(),
    'generate_time_series': GenerateTimeSeries(),
    'split_document_set_by_facet': SplitDocumentSetByFacet(),
    'find_steps_from_time_series': FindStepsFromTimeSeries(),
    'extract_document_ids': ExtractDocumentIds(),
    'query_topic_model': QueryTopicModel(),
}
