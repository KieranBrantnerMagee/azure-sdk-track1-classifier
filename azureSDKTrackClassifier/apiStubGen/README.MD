# Create API for Package Indexing

This script can be used to upload a package to APIView to generate tokens. APIView is a web app running on Azure and purpose of this web app to is generate information about public APIs in a package. We are utilizing this tool for package indexing since it already has a builtin mechanism to generate tokens for all publicly accessible APIs.

# How does it work

Script uploads given package to APIView instance which internally stores token file in azure storage account. APIView returns URL to created review if a package is processed successfully. This URL has review ID which is used to find review and blob details from COSMOS DB where review details are stored. Cosmos DB item has details like revision ID and file ID which points to blob that stores parsed tokens.

Blob will be downloaded to a json file in out directory given to script if review is created successfully.

# Usage

python.exe .\create_review.py --pkg-path <path to package file> --apikey <APIKEY> --uri "<root URL to APIViewInstance>/AutoReview/UploadAutoReview" --cosmos-cs <Cosmos connection string> --out-path <out directory> --storage-cs <storage account key>
 