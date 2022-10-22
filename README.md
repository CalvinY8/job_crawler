# job_crawler
search through jobs more efficently

how it works:
The user specifies search terms and number of pages to get from indeed.</br>
From each resulting job posting, the crawler will get 7 fields:</br>
title ,company ,location ,easilyApply ,urgentlyHiring ,summary ,link</br>

These fields are used to create a .CSV file.</br>
Uploading this data into online Amazon S3 storage will trigger a lambda function (.js)</br>
The lambda function loads the CSV data into the hosted Amazon mysql database.</br>

Software such as SQL workbench or MySQL workbench can make queries to the database, allowing faster sifting through job postings.</br>

diagram:</br>
indeed > .csv file > amazon S3 bucket > lambda function triggered > hosted Relational Database Service</br>

demo available https://youtu.be/1XDQ4QAyug0
