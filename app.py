import json

from flask import Flask, request, jsonify, render_template
from flask_restful import Api, Resource
from flask_cors import CORS

from generate_html import Initial, UsedeskApi, AsanaApi


class Integration(Resource):
    def post(self, id_=0):
        if id_ == 0:
            params = request.json
            api_usedesk = params['api_usedesk']
            api_asana = params['api_asana']
            ticket_id_from = params['ticket_id']
            field_id_from = params['field_id']
            task_list, length, workspace_projects, workspace_assignee = Initial.render_data(api_usedesk, api_asana,
                                                                                 field_id_from, ticket_id_from)
            return jsonify(html=render_template('index.html',
                                                length=length,
                                                task_list=task_list,
                                                workspace_projects=workspace_projects,
                                                workspace_assignee=workspace_assignee))

        elif id_ == 1:
            params = request.form
            task_name = request.form['taskname']

            if not task_name:
                response = {'ans': 'Введите название задачи!'}
                return json.dumps(response)

            elif 'workspace' not in params:
                response = {'ans': 'Выберите workspace!'}
                return json.dumps(response)

            elif 'project' not in params:
                response = {'ans': 'Выберите проект!'}
                return json.dumps(response)

            assignee = params['assignee'] if 'assignee' in params else None
            deadline = request.form['deadline']
            project_name = request.form['project']
            notes = request.form['notes']
            response = {'ans': AsanaApi.create_task(task_name, deadline, project_name, notes, assignee)}
            return json.dumps(response)

        elif id_ == 2:
            params = request.form
            response = {'ans': UsedeskApi.connect_task(params['task_id'])}
            return json.dumps(response)

        else:
            return "Error", 404


app = Flask(__name__)
CORS(app)
api = Api(app)
api.add_resource(Integration, "/integration_asana",
                              "/integration_asana/",
                              "/integration_asana/<int:id_>")

if __name__ == '__main__':
    app.run(debug=True)
