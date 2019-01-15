class Task(dict):

    __getattr__ = dict.__getitem__

    __setattr__ = dict.__setitem__

    __delattr__ = dict.__delitem__

    def __init__(self, task_id=None, task_type=None, task_parameters=None, result=None, parent_id=None, username=None):
        self['task_id'] = task_id
        self['task_type'] = task_type
        self['task_parameters'] = task_parameters
        self['result'] = result
        self['parent_id'] = parent_id
        self['username'] = username
