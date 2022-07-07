#set search terms on line 86
#set number of pages to crawl on line 105

import csv
import os
import requests
from requests import get
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import lxml

import urllib

import re

from time import sleep, perf_counter
from random import randint

import concurrent.futures
import threading
csv_writer_lock = threading.Lock()

MAX_THREADS = 30


#urlWithSearchTerms uses the urllib package, use function urlencode to convert non-alpha characters to url characters %&
#allows searching multiple terms

#return the URL for searching for a specified job and location
def urlWithSearchTerms(jobTerm, location):
    params = urllib.parse.urlencode({'q': jobTerm, 'l': location, 'sort': 'date'})
    url = "https://ca.indeed.com/jobs?%s" % params
    #print(url) #see url being searched.
    return url

#get the <td> containing job postings from the given URL
def getSoupFromURL(urlstring):
    page = requests.get(urlstring)
    soup = BeautifulSoup(page.text, "lxml") #lxml for speed https://stackoverflow.com/questions/25714417/beautiful-soup-and-table-scraping-lxml-vs-html-parser
    #print(soup.prettify())
    return soup

def delete_old_csv():
    csv_file_name = 'jobs.csv'
    if(os.path.exists(csv_file_name) and os.path.isfile(csv_file_name)):
        os.remove(csv_file_name)
        print('old csv removed')


def create_csv():

    url = urlWithSearchTerms("python", "vancouver") #the search terms
    #print(url)

    #---preparing the dataframe
    #setup the dataframe with columns...a mismatch will occur if the length of the job_post array doesn't match the number of columns
    #columns = ["title", "company", "location", "easilyApply", "urgentlyHiring", "summary", "link", "description"]

    #---retrieve the data
    #the outer for loop increments the pages, giving each page to the inner for loop

    urls_list = []

    for pagenumber in range(2): #enter the number of pages you want here.

        url_page = ""
        if pagenumber == 0:
            url_page = url #the first page
        else:
            url_page = url + "&start=" + str(pagenumber) + "0" #advance one page in indeed

        urls_list.append(url_page)
    
    #---list of urls created

    #---give list of urls to process_url_single() 
    threads = min(MAX_THREADS, len(urls_list))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        executor.map(process_url_single, urls_list)

    #ERROR for some reason when I run multithreading with 2 pages, it only gets 22 or 21 jobs, it should get 30 jobs

    #---tested with a simple for loop. can it get all 30 jobs? yep.
    # for url in urls_list:
    #     process_url_single(url)

#     return codecs.charmap_encode(input,self.errors,encoding_table)[0]
# UnicodeEncodeError: 'charmap' codec can't encode character '\u2010' in position 814: character maps to <undefined>


def process_url_single(url_page):

    sleep(randint(2,10))

    #print(url_page) see that url incremented correctly

    soup = getSoupFromURL(url_page) #get the code containing jobs from the rest of the html on that page.

    #WARN add some error check that prevents scraping non-existing pages(indeed doesn't have these pages)

    resultsCol = soup.find("td", {"id": "resultsCol"}) #we want only the resultsCol td
    jobsList = resultsCol.find(name="ul", attrs={"class":"jobsearch-ResultsList"})
    #print(resultsCol.prettify())
    
    #go through the 15 jobs on the page

    #the inner for loop gets all the jobs on a given page and adds them to the csv

    for jobCard in jobsList.find_all(name="div", attrs={"class":"cardOutline", "class": "tapItem"}):

        #this should run 15 times per 1 page...#ERROR only runs once per page.
        print('gotten one job post')

        #15 jobCards per page

        job_post = [] #for each job listing, make new array to hold data

        #---get title from job posting
        for h2 in jobCard.find_all("h2", attrs={"class":"jobTitle", "class": "jobTitle-newJob"}):
            #get first span inside a
            a = h2.find("a")
            span = a.find("span")
            job_post.append(span["title"])

        #---get company from job posting
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
        id_a = jobCard.find("a", class_="jcs-JobTitle")
        job_url = "https://ca.indeed.com" + id_a['href'] #link to individual job
        job_post.append(job_url)


        #using beautifulsoup instead of selenium. faster?

        individual_job_soup = getSoupFromURL(job_url)

        #wait for load
        sleep(2)

        #go find the description from the soup
        job_desc = individual_job_soup.find("div", {"id": "jobDescriptionText"})

        #somehow recursively find the inner text

        #job_desc = "--"
        if job_desc.text:
            job_post.append(job_desc.text.strip())
        else:
            job_post.append('--')

        #----printouts for testing----
        #print("page:" + str(pagenumber) + " ,columns: " + str(len(job_post))) #so, each page should have 15 entries of 8 columns each.

        # if pagenumber == 0: #if first page, show me results
        #     print("title: " + job_post[0])
        #     print("company: " + job_post[1])
        #     print("location: " + job_post[2])
        #     print("easilyApply: " + job_post[3])
        #     print("urgentlyHiring: " + job_post[4])
        #     print("summary: " + job_post[5])
        #     print("link: " + job_post[6])


        #YOU ARE HERE
        #the most vital part, using thread lock to write to the csv
        #https://stackoverflow.com/questions/66342780/python-multithreading-output-to-csv-file
        with csv_writer_lock:
            with open("jobs.csv", mode="a", encoding="utf-8") as f1: #mode="a" creates csv if not exist, otherwise appends to it
                
                writer = csv.writer(f1, delimiter=",")
                writer.writerow(job_post) #directly enter the list into the csv

                #print('appending')

                #can also use writerows for nested list
                #https://stackoverflow.com/questions/33091980/difference-between-writerow-and-writerows-methods-of-python-csv-module



def main():

    start = perf_counter()

    delete_old_csv()

    create_csv()
    #use bucket jobsdatasource
    #use lambda lambda-role-for-jobs-s3-cloudwatch
    #upload_to_bucket() #bucket no longer hosted

    end = perf_counter()
    print("total time (seconds): " + str(end-start)) # 44 seconds for 2 pages

if __name__ == "__main__":
    main()


#the main objective is to analyze job description data
#record how many hits on software , say, R, pandas, numpy, etc.
#how many hits on langauges, ex: python, C++, etc
#how many hits on years of expeirence
#and record all those number hits on csv file


languages = ["python", "R", "SQL", "Java", "Julia", "Scala", "C", "C++", "JavaScript"]
python_packages = ["TensorFlow", "NumPy", "SciPy", "Pandas", "Matplotlib", "Keras", "SciKit-Learn", "PyTorch", "Scrapy", "BeautifulSoup"]

# right now we have a block of text stored in csv column
# and I wanna run some SQL queries on the cells in that column
# and put the resulting counts into new cells

# thing is, it's gonna be a pain to run those queries by hand.

# If only there was a way to do it dynamically.


#anyway, I can probably graph the stuff by hand
#the other issue is that it's really slow to wait for things to load.
#maybe it's better to load the entire page instead of the preview.

