from werkzeug.exceptions import BadRequest
from config import Config
import requests
import os
from werkzeug.exceptions import BadRequest
from app.models import Dataset, Document, DocumentDatasetRelation
from app import db
from flask import current_app
import json

def get_dataset(dataset_name):
    dataset = Dataset.query.filter_by(dataset_name=dataset_name).one_or_none()
    if not dataset or not uptodate(dataset):
        request_dataset(dataset_name)
    return Dataset.query.filter_by(dataset_name=dataset_name).first()


def get_token():
    # TODO get token once and require only in case of authentication error   
    url = os.path.join(Config.DATASET_URI, "authenticate")
    payload = json.dumps({"email":Config.DATASET_EMAIL, "password":Config.DATASET_PASSWORD})
    headers = {'content-type': 'application/json'}
    response = requests.request("POST", url, data=payload, headers=headers, verify=False)
    token =  response.json()["auth_token"]
    return "JWT " + token
    

def uptodate(dataset):
    return dataset.hash_value == get_hash_value(dataset.dataset_name)
    
def get_hash_value(dataset_name):
    url = os.path.join(Config.DATASET_URI, "list_datasets")
    payload = json.dumps({"email":Config.DATASET_EMAIL})
    headers = {
    'content-type': "application/json",
    'authorization': get_token()
    }
    response = requests.request("POST", url, data=payload, headers=headers, verify=False)
    for d in response.json():
        if d[0] == dataset_name:
            return d[1]
    raise BadRequest("Dataset {} not found for {}".format(dataset_name, Config.DATASET_EMAIL))

                     
def request_dataset(dataset_name):
    url = os.path.join(Config.DATASET_URI, "get_dataset_content")
    payload = json.dumps({"email":Config.DATASET_EMAIL, "dataset_name":dataset_name})
    headers = {
    'content-type': "application/json",
    'authorization': get_token()
    }

    response = requests.request("POST", url, data=payload, headers=headers, verify=False)
    make_dataset(dataset_name, response.json())

def make_dataset(dataset_name, document_list):
    dataset = Dataset.query.filter_by(dataset_name=dataset_name).one_or_none()
    if dataset:
        DocumentDatasetRelation.query.filter_by(dataset_id = dataset.id).delete()
    else:
        dataset = Dataset(dataset_name=dataset_name,
                          hash_value=get_hash_value(dataset_name))
        db.session.add(dataset)
    db.session.commit()

    relations = []
    for d in document_list:
        if d["type"] != "article":
            # TODO: add all documents from this issues?
            # for now: skip
            continue
        document = get_document(d["id"])
        relations.append(DocumentDatasetRelation(dataset_id = dataset.id,
                                           document_id = document.id,
                                           relevance = d["relevancy"]))
    db.session.add_all(relations)
    db.session.commit()


def get_document(document_id):
    document = Document.query.filter_by(solr_id = document_id).one_or_none()
    if not document:
        document = Document(solr_id = document_id)
        db.session.add(document)
        db.session.commit()
    return document
            
        
                          
    
