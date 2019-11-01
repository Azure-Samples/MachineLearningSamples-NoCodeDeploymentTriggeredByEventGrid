import json
import logging
import os

import azure.functions as func
from azureml.core import Workspace, Model, Environment
from azureml.core.authentication import ServicePrincipalAuthentication
from azureml.core.model import InferenceConfig
from azureml.core.webservice.aci import AciServiceDeploymentConfiguration

def main(event: func.EventGridEvent):
    result = json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
    })

    logging.info('Python EventGrid trigger processed an event: %s', result)

    # get service principal from env variables
    sp_auth = ServicePrincipalAuthentication(
        tenant_id=os.getenv('TENANT_ID', ''),
        service_principal_id=os.getenv('SP_ID', ''),
        service_principal_password=os.getenv('SP_PASSWORD', ''))
    
    # parse azure subscription ID, resource group name, and ML workspace name from event grid event topic
    sub_tag="subscriptions"
    rg_tag="resourceGroups"
    ws_provider_tag="providers/Microsoft.MachineLearningServices/workspaces"

    subscription_id = event.topic.split("{}/".format(sub_tag), 1)[1].split("/{}".format(rg_tag), 1)[0]
    resource_group_name = event.topic.split("{}/".format(rg_tag), 1)[1].split("/{}".format(ws_provider_tag), 1)[0]
    workspace_name = event.topic.split("{}/".format(ws_provider_tag), 1)[1].split("/", 1)[0]

    # get workspace
    ws = Workspace.get(
        name=workspace_name,
        auth=sp_auth,
        subscription_id=subscription_id,
        resource_group=resource_group_name)

    logging.info(
        'SubscriptionID = %s; ResourceGroup = %s; WorkSpace = %s; Location = %s',
        ws.subscription_id,
        ws.resource_group,
        ws.name,
        ws.location)
    
    # get model from event data
    event_data = event.get_json()
    model_id = '{}:{}'.format(event_data['modelName'], event_data['modelVersion'])
    model = Model(ws, id=model_id)
    logging.info('Model name = %s', model.name)

    # perform no code deploy, in a fire-n-forget way, as we don't need to hold the Functions App resource and we will 
    # respond to event grid request in time so that Event Grid won't timeout and retry.
    service_name = 'acitest-{}-{}'.format(event_data['modelName'], event_data['modelVersion'])
    service = Model.deploy(ws, service_name, [model])
    logging.info('Start deploying service %s to ACI', service.name)
