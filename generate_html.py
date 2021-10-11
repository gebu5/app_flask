import requests
import configparser

import asana


class Initial:
    """Класс содержащий конфиг и переменные для всех функций."""
    asana_token = ''
    usedesk_token = ''
    ticket_id = ''
    field_id = 0
    config = configparser.ConfigParser()
    config.read('constants.ini')

    @staticmethod
    def render_data(api_usedesk, api_asana, field_id_from, ticket_id_from):
        """Единственная функция в этом классе, срабатывает при запросе блока на эндпоинт и возвращает html-код."""
        Initial.usedesk_token = api_usedesk
        Initial.ticket_id = ticket_id_from
        Initial.asana_token = api_asana
        Initial.field_id = int(field_id_from)
        task_list = []
        workspace_projects, workspace_assignee = AsanaApi.gid_render('render')
        task_gid = UsedeskApi.customfield_usedesk()
        if task_gid:
            task_gid_list = task_gid.split(',')
        else:
            task_list.append({'name': ''})
            return task_list, 0, workspace_projects, workspace_assignee

        for task_gid in task_gid_list:
            AsanaApi.get_task_data('get_task_data', task_gid, task_list)

        return task_list, len(task_gid_list), workspace_projects, workspace_assignee


class UsedeskApi:
    """Класс содержащий функции для работы с Usedesk."""
    @staticmethod
    def customfield_usedesk():
        """Функция возвращает значение доп поля в тикете Usedesk."""
        to_json = {'api_token': Initial.usedesk_token, 'ticket_id': Initial.ticket_id}
        r = requests.post(Initial.config['host']['usedesk'] +
                          Initial.config['method']['get_ticket'],
                          json=to_json)

        custom_list = r.json()
        field_values = ''
        if 'custom_fields' not in custom_list:
            return field_values
        for custom_field in custom_list['custom_fields']:
            if custom_field['ticket_field_id'] == Initial.field_id:
                field_values = custom_field['value']

        return field_values

    @staticmethod
    def comment_for_usedesk(field_values, message):
        """Функция отправляющая внутренний комментарий в наш тикет."""
        to_update = {
            'api_token': Initial.usedesk_token,
            'ticket_id': Initial.ticket_id,
            'field_id': Initial.field_id,
            'field_value': field_values
        }
        requests.post(Initial.config['host']['usedesk'] +
                      Initial.config['method']['update_ticket'],
                      json=to_update)

        to_comment = {'api_token': Initial.usedesk_token, 'ticket_id': Initial.ticket_id, 'message': message}
        requests.post(Initial.config['host']['usedesk'] +
                      Initial.config['method']['comment_ticket'],
                      json=to_comment)

    @staticmethod
    def connect_task(task_id):
        """Функция для прикрепления задачи из Асаны к тикету."""
        client = asana.Client.access_token(Initial.asana_token)
        try:
            client.tasks.get_task(task_id, opt_pretty=True)
        except:
            return "Задача не найдена"

        field_values = UsedeskApi.customfield_usedesk()
        if field_values:
            field_values += ',' + task_id
        else:
            field_values = task_id
        task = AsanaApi.get_task_data('connect', task_id)
        message = (f'Прикреплена задача - {task["name"]}\n'
                   f'Статус - {task["status"]}\n'
                   f'Исполнитель - {task["assignee"]}\n'
                   f'Дедлайн - {task["deadline"]}\n'
                   f'Проект - {task["project"]}\n'
                   f'Описание - {task["notes"]}')
        UsedeskApi.comment_for_usedesk(field_values, message)

        return "Success"


class AsanaApi:
    """Класс содержащий функции для работы с сайтом Асаны."""
    @staticmethod
    def parsing_task_data(result, subtask):
        """Функция возвращает всю информацию о задаче из Асаны."""
        url_task = (f'{Initial.config["host"]["asana"]}'
                    f'{result["memberships"][0]["project"]["gid"]}/'
                    f'{result["gid"]}')

        assignee_name = result['assignee']['name'] if result['assignee'] else 'Не назначен'

        status = result['completed']
        status = 'Выполнена' if status else 'Не выполнена'

        project_name = result['memberships'][0]['project']['name']
        description = result['notes']
        deadline = result['due_on']
        task_name = result['name']
        custom_list = AsanaApi.custom_field_asana(result)
        subtask_list = AsanaApi.subtask_asana(result, subtask)

        task_parsed = {
            'name': task_name, 'status': status, 'assignee': assignee_name,
            'deadline': deadline, 'project': project_name,
            'custom_fields': custom_list, 'notes': description,
            'subtask_list': subtask_list, 'url': url_task
        }

        return task_parsed

    @staticmethod
    def custom_field_asana(result):
        """Функция для получения доп полей в задаче Асаны."""
        custom_list = []
        if not 'custom_fields' in result.keys():
            return custom_list
        for field in result['custom_fields']:
            field_name = field['name']

            if 'enum_value' not in field.keys():
                value = field['text_value'] if field['type'] == 'text' else field['number_value']
            else:
                value = None if field['enum_value'] is None else field['enum_value']['name']

            if value:
                to_append = {field_name: value}
                custom_list.append(to_append)
        return custom_list

    @staticmethod
    def subtask_asana(result, subtask):
        """Функция для получения подзадач в задаче Асаны."""
        subtask_list = []
        subtask = list(subtask)
        if not subtask:
            return subtask_list
        project_gid = result['memberships'][0]['project']['gid']
        for sub in subtask:
            subtask_gid = sub['gid']
            url_subtask = f'{Initial.config["host"]["asana"]}{project_gid}/{subtask_gid}'
            subtask_parsed = {sub['name']: url_subtask}
            subtask_list.append(subtask_parsed)
        return subtask_list

    @staticmethod
    def create_task(taskname, deadline, project_name, notes, assignee):
        """Функция для создания новой задачи в Асане."""
        client = asana.Client.access_token(Initial.asana_token)
        projects_gid_dict, assignee_gid_dict = AsanaApi.gid_render('gid')
        project_gid = projects_gid_dict[project_name]
        assignee_gid = assignee_gid_dict[assignee] if assignee else None

        task = {
            'name': taskname,
            'assignee': assignee_gid,
            'due_on': deadline,
            'projects': project_gid,
            'notes': notes
        }

        try:
            result_create = client.tasks.create_task(task, opt_pretty=True)
        except asana.error.InvalidRequestError:
            return "Неправильно введен дедлайн!"

        field_values = UsedeskApi.customfield_usedesk()
        if field_values:
            field_values += ',' + result_create['gid']
        else:
            field_values = result_create['gid']
        message = (f'Создана задача - {taskname}\n'
                   f'Статус - Не выполнен\n'
                   f'Исполнитель - {assignee}\n'
                   f'Дедлайн - {deadline}\n'
                   f'Проект - {project_name}\n'
                   f'Описание - {notes}')

        UsedeskApi.comment_for_usedesk(field_values, message)

        return "Success"

    @staticmethod
    def workspace_projects_assignee(client, workspace_projects, workspace_assignee, projects_gid, assignee_gid):
        """Функция для получения списка всех workspace Асаны."""
        workspaces_list = client.workspaces.get_workspaces(opt_pretty=True)
        for workspace in list(workspaces_list):
            AsanaApi.projects_for_workspace(client, workspace, workspace_projects, projects_gid)
            AsanaApi.assignee_for_workspace(client, workspace, workspace_assignee, assignee_gid)

    @staticmethod
    def projects_for_workspace(client, workspace, workspace_projects, projects_gid):
        """Функция для получения всех проектов Асаны."""
        projects_list = client.projects.get_projects_for_workspace(workspace['gid'], opt_pretty=True)
        project_names = []
        for project in list(projects_list):
            project_names.append(project['name'])
            projects_gid[project['name']] = project['gid']

        dict_projects = {workspace['name']: project_names}
        workspace_projects.append(dict_projects)

    @staticmethod
    def assignee_for_workspace(client, workspace, workspace_assignee, assignee_gid):
        """Функция для получения всех исполнителей в Асане."""
        assignee_list = client.workspace_memberships.get_workspace_memberships_for_workspace(workspace['gid'],
                                                                                             opt_pretty=True)
        assignee_names = []
        for assignee in list(assignee_list):
            assignee_names.append(assignee['user']['name'])
            assignee_gid[assignee['user']['name']] = assignee['user']['gid']

        dict_assignee = {workspace['name']: assignee_names}
        workspace_assignee.append(dict_assignee)

    @staticmethod
    def get_task_data(query, task_gid, task_list=[]):
        """Функция возвращает информацию о задаче для прикрепления,
        или добавляет в список задач всю информацию о конкретной задаче."""
        client = asana.Client.access_token(Initial.asana_token)
        try:
            result = client.tasks.get_task(task_gid, opt_pretty=True)
            subtask = client.tasks.get_subtasks_for_task(task_gid, opt_pretty=True)
        except:
            task_list.append({'name': ''})
            return task_list

        if query == 'connect':
            return AsanaApi.parsing_task_data(result, subtask)
        elif query == 'get_task_data':
            task_data = AsanaApi.parsing_task_data(result, subtask)
            task_list.append(task_data)

    @staticmethod
    def gid_render(query):
        """Функция возвращает либо список всех айди проектов и исполнителей Асаны,
        либо список воркспейсов,проектов и исполнителей для рендера html шаблона."""
        client = asana.Client.access_token(Initial.asana_token)
        workspace_projects = []
        workspace_assignee = []
        projects_gid = {}
        assignee_gid = {}

        AsanaApi.workspace_projects_assignee(client, workspace_projects, workspace_assignee, projects_gid, assignee_gid)

        if query == 'gid':
            return projects_gid, assignee_gid
        elif query == 'render':
            return workspace_projects, workspace_assignee
