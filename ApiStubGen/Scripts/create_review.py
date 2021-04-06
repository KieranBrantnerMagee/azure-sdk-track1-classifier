import requests
import argparse
import os
import sys
import logging
import codecs
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient

QUERY = "SELECT r.Revisions FROM Reviews r where r.id = '{}'"
COSMOS_DB_NAME = "APIView"
COSMOS_REVIEW_CONTAINER = "Reviews"
STORAGE_FILE_CONTAINER = "codefiles"

# Create cosmosdb clients
def get_db_client(connection_string):
    # Create cosmosdb client
    cosmos_client = CosmosClient.from_connection_string(connection_string)
    if not cosmos_client:
        logging.error("Failed to create cosmos client for db")
        exit(1)

    logging.info("Created cosmos client for cosmosdb")
    # Create database client object using CosmosClient
    db_client = None
    try:
        db_client = cosmos_client.get_database_client(COSMOS_DB_NAME)
        logging.info("Created database clients")
    except:
        logging.error("Failed to create databae client using CosmosClient")
        traceback.print_exc()
        exit(1)
    return db_client


# Fetch Review details from Cosmos DB
def get_review_details(review_id, cosmos_conn_string):
    db_client = get_db_client(cosmos_conn_string)
    container_client = db_client.get_container_client("Reviews")
    query_string = QUERY.format(review_id)
    items = container_client.query_items(query=query_string, enable_cross_partition_query=True)
    last_revision = None
    for r in items:
        last_revision = r['Revisions'][0]
    return last_revision['id'], last_revision['Files'][0]['ReviewFileId']


def get_blob_contents(container_client, blob_name):
    contents = codecs.decode(container_client.get_blob_client(blob_name).download_blob().content_as_bytes(), 'utf-8-sig')
    return contents
     

# Download blob
def download_blob(revision_id, file_id, connection_string, out_path):
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(STORAGE_FILE_CONTAINER)
    blob_name = revision_id + "/" + file_id
    contents = get_blob_contents(container_client, blob_name)
    filePath = os.path.join(out_path, file_id+".json")
    f = open(filePath, "w")
    f.write(contents)
    f.close()
    print("Token file is downloaded to {}".format(filePath))
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run apistubgen against target folder. "
    )

    parser.add_argument(
        "--uri",
        dest="api_uri",
        help="URI to APIView web app",
        required=True,
    )

    parser.add_argument(
        "--pkg-path",
        dest="pkg_path",
        help="Path to package that needs to be uploaded to APIView",
        required=True,
    )

    parser.add_argument(
        "--cosmos-cs",
        dest="cosmos_cs",
        help="Connection string to cosmos DB"
    )

    parser.add_argument(
       "--storage-cs",
        dest="storage_cs",
        help="Connection string to storage account"
    )

    parser.add_argument(
        "--apikey",
        dest="apikey",
        help="API Key to APIView web app",
        required=True,
    )

    parser.add_argument(
        "--out-path",
        dest="out_path",
        help="Output directory",
        required=True,
    )

    args = parser.parse_args()

    #url='http://localhost:5000/AutoReview/UploadAutoReview'
    files = {'file': open(args.pkg_path, 'rb')}
    values = {'label': 'Test'}
    headers = {'ApiKey': args.apikey}
    r = requests.post(args.api_uri, files=files, data=values, headers=headers)
    print(r.status_code, r.text)
    if r.status_code == 201:
        print("API Review created with link {}".format(r.text))
    else:
        print("Failed to create review")
        sys.exit(1)

    review_id = r.text.split("/")[-1]
    print("Review ID is {}".format(review_id))
    revision_id, file_id = get_review_details(review_id, args.cosmos_cs)
    if revision_id and file_id:
        print(revision_id, file_id)
        download_blob(revision_id, file_id, args.storage_cs, args.out_path)
    else:
        print("Review revision and/or File id are not available for review {}".format(review_id))
        sys.exit(1)

