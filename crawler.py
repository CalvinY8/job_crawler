#crawl multiple pages...set search terms on line 64
#set number of pages to crawl on line 59

import os
import requests
from requests import get
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import lxml

import urllib

import re

from time import sleep
from random import randint

#---for uploading csv data to aws mysql
import boto3
import logging
from botocore.exceptions import ClientError

headers = {"Accept-Language": "en-US, en;q=0.5"}
#-----


#---for uploading to s3 automatically
from botocore.exceptions import NoCredentialsError


def upload_to_bucket():

    bucket = 'lambda-csv-data-source'
    s3_file = 'csvdata/jobs.csv'

    #access the profile from ~/.aws/credentials
    session = boto3.Session(profile_name='default')
    s3 = session.client('s3')

    #delete prev. version of this file
    response = s3.delete_object(Bucket = bucket, Key = s3_file)
    #print(response)

    #try to upload file
    try:
        response = s3.upload_file("jobs.csv", bucket, s3_file)
    except ClientError as e:
        logging.error(e)
        return False
    return True




#urlWithSearchTerms uses the urllib package, use function urlencode to convert non-alpha characters to url characters %&
#allows searching multiple terms

#return the URL for searching for a specified job and location
def urlWithSearchTerms(jobTerm, location):
    params = urllib.parse.urlencode({'q': jobTerm, 'l': location, 'sort': 'date'})
    url = "https://ca.indeed.com/jobs?%s" % params
    #print(url) #see url being searched.
    return url

#get the <td> containing job postings from the given URL
def getJobsFromURL(urlstring):
    page = requests.get(urlstring)
    soup = BeautifulSoup(page.text, "lxml")
    #print(soup.prettify())
    resultsCol = soup.find("td", {"id": "resultsCol"}) #we want only the resultsCol td
    jobsList = resultsCol.find(name="ul", attrs={"class":"jobsearch-ResultsList"})
    #print(resultsCol.prettify())
    #go through the 15 jobs on the page
    return jobsList

def delete_old_csv():
    csv_file_name = 'jobs.csv'
    if(os.path.exists(csv_file_name) and os.path.isfile(csv_file_name)):
        os.remove(csv_file_name)
        print('old csv removed')

def create_csv():
    #---preparing the dataframe
    #setup the dataframe with columns...a mismatch will occur if the length of the job_post array doesn't match the number of columns
    columns = ["title", "company", "location", "easilyApply", "urgentlyHiring", "summary", "link"]

    #sample_df means sample dataframe
    #sample_df = pd.DataFrame(columns = columns)



    #---retrieve the data
    #the outer for loop increments the pages, giving each page to the inner for loop
    url = urlWithSearchTerms("python", "vancouver") #the search terms
    #print(url)

    for pagenumber in range(2): #enter the number of pages you want here.

        sleep(randint(2,10))

        page = ""
        if pagenumber == 0:
            page = requests.get(url) #the first page
        else:
            page = requests.get(url + "&start=" + str(pagenumber-1) + "0") #the format to advance one page in indeed
        
        soup = BeautifulSoup(page.text, 'html.parser')

        jobsList = getJobsFromURL(url) #get the code containing jobs from the rest of the html on that page.

        #the inner for loop gets all the jobs on a given page and adds them to the csv

        for jobCard in jobsList.find_all(name="div", attrs={"class":"cardOutline", "class": "tapItem"}):

            #15 jobCards per page

            job_post = [] #for each job listing, make new array to hold data

            #num = (len(sample_df) + 1)
            #print(num) #tested that csv row number successfully increments.

            #---get title from job posting
            for h2 in jobCard.find_all("h2", attrs={"class":"jobTitle", "class": "jobTitle-newJob"}):
                #get first span inside a
                a = h2.find("a")
                span = a.find("span")
                job_post.append(span["title"])

            #---get company from job posting
            #ERROR sometimes companyName will be "Canonical-Jobs"
            companyInfo = jobCard.find("div", attrs = {"class" : ["company_location", "tapItem-gutter", "companyInfo"]}) #15 results
            companyName_span = companyInfo.find("span", attrs={"class": "companyName"})
            #company name will be contained within the span directly, as text

            #or, company name will be containend within an <a> inside the span, as text
            companyName_a = companyInfo.find("a", attrs={"class": ["turnstileLink", "companyOverviewLink"]})

            try:
                job_post.append(companyName_span.text)

            except AttributeError: #meaning name should be held in the <a> tag                
                job_post.append(companyName_a.text)

            #---get location from job posting...location could be in a jobCard or a span, this function will find any element of class location
            companyLocation_span = companyInfo.find("div", attrs={"class": "companyLocation"})
            job_post.append(companyLocation_span.text)

            #---get easilyApply from job posting
            spans = jobCard.find_all("span", class_="iaIcon")
            if len(spans) > 0: #if not 0, a <span> was found of class iaiconActive, from inspection this class of span contains text: "easily applicable"
                for span in spans:
                    job_post.append('y')
            else:
                job_post.append("n")#not easily appliable

            #--get urgentlyHiring
            #WARN: still broken
            tds = jobCard.find_all("td", class_="urgentlyHiring")
            if len(tds) > 0:
                for span in tds:
                    job_post.append('y')
            else:
                job_post.append("n") #not urgently hiring

            #--get summary
            fulltext = "" #store in string
            summary_div = jobCard.find('div', class_="job-snippet")
            summary_ul = summary_div.find('ul')
            summary_li_resultSet = summary_div.find_all('li')

            for line in summary_li_resultSet:
                commaRemovedSummary = line.text.replace(',', '') #remove the commas from the summary for successful JSON parsing
                fulltext += commaRemovedSummary.strip()

            job_post.append(fulltext)

            #--get link
            for a in jobCard.find_all("a", class_="jcs-JobTitle"):
                job_post.append("https://ca.indeed.com" + a['href'])

            #----printouts for testing----
            #print("page:" + str(pagenumber) + " ,columns: " + str(len(job_post))) #so, each page should have 15 entries of 7 columns each.

            if pagenumber == 0: #if first page, show me results
                print("title: " + job_post[0])
                print("company: " + job_post[1])
                print("location: " + job_post[2])
                print("easilyApply: " + job_post[3])
                print("urgentlyHiring: " + job_post[4])
                print("summary: " + job_post[5])
                print("link: " + job_post[6])

    #         #still within the for loop, append arr containing info of one job post, to a new row in the dataframe
    #         #each loop, the number is incremented (see line 136)
    #         sample_df.loc[num] = job_post


    # #---outside both for loops, when all jobs scraped for all pages,
    # #  save data to csv with relative filepath

    # #but first clear the previously made csv file, so that each time the program is run, the results are like new
    # filename = "jobs.csv"
    # f = open(filename, "w+")
    # f.close()


    # #now save to csv with relative filepath
    # sample_df.to_csv("jobs.csv", encoding='utf-8')

    print('new csv data loaded')

def main():

    delete_old_csv()

    sleep(2)

    create_csv()
    #use bucket jobsdatasource
    #use lambda lambda-role-for-jobs-s3-cloudwatch
    #upload_to_bucket() #bucket no longer hosted

if __name__ == "__main__":
    main()