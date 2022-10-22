# job_crawler
search through jobs more efficently

how it works:
The user specifies search terms and number of pages to get from indeed.
From each resulting job posting, the crawler will get 7 fields:
title ,company ,location ,easilyApply ,urgentlyHiring ,summary ,link

These fields are used to create a .CSV file.
Uploading this data into online Amazon S3 storage will trigger a lambda function (.js)
The lambda function loads the CSV data into the hosted Amazon mysql database.

Software such as SQL workbench or MySQL workbench can make queries to the database, allowing faster sifting through job postings.

diagram:
indeed > .csv file > amazon S3 bucket > lambda function triggered > hosted Relational Database Service

demo available https://youtu.be/1XDQ4QAyug0
