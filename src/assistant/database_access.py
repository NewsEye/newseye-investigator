import asyncio
import aiohttp
import psycopg2
from psycopg2.extras import Json, execute_values, register_uuid
import uuid


class BlacklightAPI(object):

    def __init__(self):
        self.baseUri = "https://demo.projectblacklight.org/catalog.json"
        self.default_params = {
            'utf8': "%E2%9C%93",
        }

    async def fetch(self, session, params={}):
        async with session.get(url=self.baseUri, params=self.fix_query_for_aiohttp(params)) as response:
            return await response.json()

    # Runs the query/queries using aiohttp. The return value is a list containing the results in the corresponding order.
    async def async_query(self, queries):
        query_is_a_list = type(queries) is list
        if not query_is_a_list:
            queries = [queries]
        tasks = []
        async with aiohttp.ClientSession() as session:
            for query in queries:
                params = self.default_params.copy()
                params.update(query)
                print("Log, appending query: {}".format(params))
                tasks.append(self.fetch(session, params))
            results = await asyncio.gather(*tasks)
        print("Queries finished, returning results")
        return results

    # Unlike the requests package, aiohttp doesn't support key: [value_list] pairs for defining multiple values for
    # a single parameter. Instead, a list of (key, value) tuples is used.
    def fix_query_for_aiohttp(self, query):
        new_query = []
        for key in query.keys():
            if type(query[key]) is list:
                new_query.extend([(key, value) for value in query[key]])
            else:
                new_query.append((key, query[key]))
        return new_query


class PSQLAPI(object):

    def __init__(self):
        self._conn = psycopg2.connect("dbname=investigator")
        register_uuid()

    def add_user(self, username):
        try:
            with self._conn as conn:
                with conn.cursor() as curs:
                    curs.execute("""
                        INSERT INTO users (username)
                        VALUES (%s)
                    """, [username])
        except psycopg2.IntegrityError:
            raise TypeError("Error creating user {}: username already in use!")

    def get_last_login(self, username):
        with self._conn as conn:
            with conn.cursor() as cur:
                cur.execute("""
                SELECT last_login FROM users
                WHERE username = %s
                """, [username])
                last_login = cur.fetchall()
        return last_login[0][0]

    def set_last_login(self, username, time):
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    UPDATE users
                    SET last_login = %s
                    WHERE username = %s
                """, [time, username])

    def set_current_task(self, username, task_id):
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    UPDATE users
                    SET current_task = %s
                    WHERE username = %s
                """, [task_id, username])

    def get_current_task_id(self, username):
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    SELECT current_task
                    FROM users
                    WHERE username = %s
                """, [username])
                current_task_id = curs.fetchone()
        if not current_task_id:
            return None
        return current_task_id[0]

    def get_current_task(self, username):
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    UPDATE task_results
                    SET last_accessed = NOW()
                    FROM task_history h
                    INNER JOIN task_results r
                    ON h.task_type = r.task_type
                    AND h.task_parameters = r.task_parameters
                    WHERE task_id = (
                        SELECT current_task
                        FROM users
                        WHERE username = %s
                    )
                    RETURNING task_id, h.task_type, h.task_parameters, r.task_result, r.result_id, parent_id
                """, [username])
                current_task = curs.fetchone()
        if not current_task:
            return None
        return dict(zip(['task_id', 'task_type', 'task_parameters', 'task_result', 'result_id', 'parent_id'], current_task))

    def get_task_by_id(self, username, task_id):
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    UPDATE task_results r
                    SET last_accessed = NOW()
                    FROM task_history h
                    INNER JOIN r
                    ON h.task_type = r.task_type
                    AND h.task_parameters = r.task_parameters
                    WHERE task_id = %s
                    AND user_id = (
                        SELECT user_id
                        FROM users
                        WHERE username = %s
                    )
                    RETURNING task_id, h.task_type, h.task_parameters, task_result, result_id, parent_id
                """, [task_id, username])
                query = curs.fetchone()
        if not query:
            return None
        return dict(zip(['task_id', 'task_type', 'task_parameters', 'task_result', 'result_id', 'parent_id'], query))

    def get_results_by_id(self, result_ids):
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    UPDATE task_results r
                    SET last_accessed = NOW()
                    WHERE result_id IN %s
                    RETURNING result_id, task_type, task_parameters, task_result
                """, [tuple(result_ids)])
                results = curs.fetchall()
        if not results:
            return None
        return dict([(str(result[0]), dict(zip(['result_id', 'task_type', 'task_parameters', 'task_result'], result))) for result in results])

    def get_results_by_task_id(self, task_ids):
        if type(task_ids) is not list:
            task_ids = [task_ids]
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    UPDATE task_results tr
                    SET last_accessed = NOW()
                    FROM (
                        SELECT h.task_id, h.task_type, h.task_parameters, r.task_result, r.result_id, r.created_on, r.last_updated, r.last_accessed
                        FROM task_results r
                        INNER JOIN task_history h
                        ON r.task_type = h.task_type
                        AND r.task_parameters = h.task_parameters
                        WHERE h.task_id IN %s
                    ) AS e (task_id, task_type, task_parameters, task_result, result_id, created_on, last_updated, last_accessed)
                    WHERE tr.result_id = e.result_id
                    RETURNING e.task_id, e.task_type, e.task_parameters, e.task_result, e.created_on, e.last_updated, e.last_accessed
                """, [tuple(task_ids)])
                results = curs.fetchall()
        if not results:
            return None
        return dict([(str(result[0]), dict(zip(['task_id', 'task_type', 'task_parameters', 'task_result', 'created_on', 'last_updated', 'last_accessed'], result))) for result in results])

    def get_user_tasks_by_query(self, username, queries):
        with self._conn as conn:
            with conn.cursor() as curs:
                execute_values(curs, """
                    UPDATE task_history th
                    SET last_accessed = NOW()
                    FROM (
                        SELECT h.task_id, h.task_type, h.task_parameters, h.parent_id, data.username
                        FROM task_history h
                        INNER JOIN (VALUES %s) AS data (username, task_type, task_parameters)
                        ON h.task_type = data.task_type
                        AND h.task_parameters = data.task_parameters
                        AND h.user_id = (
                            SELECT user_id FROM users WHERE users.username = data.username
                        )
                    ) AS e (task_id, task_type, task_parameters, parent_id, username)
                    WHERE e.task_id = th.task_id
                    RETURNING e.task_id, e.task_type, e.task_parameters, e.parent_id
                """, [(username, query[0], Json(query[1])) for query in queries], template='(%s, %s, %s::jsonb)')
                tasks = curs.fetchall()
        if not tasks:
            return None
        return [(task[0], (task[1], task[2]), task[3]) for task in tasks]

    # Todo: update to same output format as above??
    def get_results_by_query(self, queries):
        with self._conn as conn:
            with conn.cursor() as curs:
                execute_values(curs, """
                    UPDATE task_results tr
                    SET last_accessed = NOW()
                    FROM (VALUES %s) AS data (task_type, task_parameters)
                    WHERE tr.task_type = data.task_type
                    AND tr.task_parameters = data.task_parameters
                    RETURNING tr.task_type, tr.task_parameters, tr.task_result
                """, [(query[0], Json(query[1])) for query in queries], template='(%s, %s::jsonb)')
                result = curs.fetchall()
        if not result:
            return None
        return [((item[0], item[1]), item[2]) for item in result]

    # TODO: Should this update the last_accessed field??
    def get_user_history(self, username):
        with self._conn as conn:
            with conn.cursor() as curs:
                curs.execute("""
                    SELECT task_id, h.task_type, h.task_parameters, task_result, parent_id 
                    FROM task_history h
                    INNER JOIN task_results r
                    ON h.task_type = r.task_type
                    AND h.task_parameters = r.task_parameters
                    WHERE
                        user_id = (
                            SELECT user_id FROM users WHERE username = %s
                        )
                """, [username])
                queries = curs.fetchall()
        if not queries:
            return None
        history = {}
        for item in queries:
            history[item[0]] = dict(zip(['task_id', 'task_type', 'task_parameters', 'task_result', 'parent_id'], item))
        return history

    def add_tasks(self, task_list):
        task_list = [(task['task_type'], task['username'], Json(task['task_parameters']), task['parent_id']) for task in task_list]
        id_list = [uuid.uuid4() for task in task_list]
        while True:
            try:
                with self._conn as conn:
                    with conn.cursor() as curs:
                        execute_values(curs, """
                            INSERT INTO task_history (task_id, task_type, task_parameters, parent_id, user_id)
                            SELECT task_id, task_type, task_parameters, parent_id, user_id
                            FROM users INNER JOIN (VALUES %s) AS data (task_id, task_type, username, task_parameters, parent_id)
                            ON users.username = data.username
                            ON CONFLICT ON CONSTRAINT task_history_user_id_parent_id_task_type_task_parameters_key
                            DO UPDATE
                            SET created_on = NOW()
                        """, [(i, *q) for i, q in zip(id_list, task_list)], template='(%s::uuid, %s, %s, %s::jsonb, %s::uuid)')
                        break
            except psycopg2.IntegrityError:
                id_list = [uuid.uuid4() for task in task_list]
        return id_list

    # Todo: Rename this
    def add_results(self, task_list):
        task_list = [(item['task_type'], Json(item['task_parameters']), Json(item['task_result'])) for item in task_list]
        while True:
            try:
                with self._conn as conn:
                    with conn.cursor() as curs:
                        execute_values(curs, """
                            INSERT INTO task_results (task_type, task_parameters, task_result)
                            SELECT task_type, task_parameters, task_result
                            FROM (VALUES %s) AS data (task_type, task_parameters, task_result)
                        """, task_list, template='(%s, %s::jsonb, %s::json)')
                        break
            except psycopg2.IntegrityError:
                # Todo: make sure that this works without having to call some rollback method
                pass

    def update_results(self, task_list):
        with self._conn as conn:
            with conn.cursor() as curs:
                execute_values(curs, """
                    UPDATE task_results tr
                    SET task_result = data.task_result,
                        last_updated = NOW(), 
                        last_accessed = NOW()
                    FROM (VALUES %s) AS data (task_type, task_parameters, task_result)
                    WHERE tr.task_type = data.task_type
                    AND tr.task_parameters = data.task_parameters 
                """, [(task['task_type'], Json(task['task_parameters']), Json(task['task_result'])) for task in task_list], template='(%s, %s::jsonb, %s::json)')
