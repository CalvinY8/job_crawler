#crawl multiple pages...set search terms on line 86
#set number of pages to crawl on line 104

import os
import requests
from requests import get
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import lxml

import urllib

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import re

from time import sleep, perf_counter
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
    columns = ["title", "company", "location", "easilyApply", "urgentlyHiring", "summary", "link", "description"]

    #sample_df means sample dataframe
    sample_df = pd.DataFrame(columns = columns)

    fire_fox_options = webdriver.FirefoxOptions()
    fire_fox_options.headless = True #---comment out this line to see UI
    driver = webdriver.Firefox(options = fire_fox_options)
    driver.get(url)

    #---retrieve the data
    #the outer for loop increments the pages, giving each page to the inner for loop

    for pagenumber in range(2): #enter the number of pages you want here.

        sleep(randint(2,10))

        url_page = ""
        if pagenumber == 0:
            url_page = url #the first page
        else:
            url_page = url + "&start=" + str(pagenumber) + "0" #advance one page in indeed

        #print(url_page) see that url incremented correctly

        soup = getSoupFromURL(url_page) #get the code containing jobs from the rest of the html on that page.

        resultsCol = soup.find("td", {"id": "resultsCol"}) #we want only the resultsCol td
        jobsList = resultsCol.find(name="ul", attrs={"class":"jobsearch-ResultsList"})
        #print(resultsCol.prettify())
        
        #go through the 15 jobs on the page

        #the inner for loop gets all the jobs on a given page and adds them to the csv

        for jobCard in jobsList.find_all(name="div", attrs={"class":"cardOutline", "class": "tapItem"}):

            #15 jobCards per page

            job_post = [] #for each job listing, make new array to hold data

            num = (len(sample_df) + 1)
            #print(num) #tested that csv row number successfully increments.

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
            for a in jobCard.find_all("a", class_="jcs-JobTitle"):
                job_post.append("https://ca.indeed.com" + a['href'])


            #YOU ARE HERE
            #---get data from iframe
            #open the new page directly
            # use selenium to access content in the iframe

            #get the <a> of class jcs-JobTitle
            id_a = jobCard.find("a", class_="jcs-JobTitle")
            value1 = id_a['data-jk']
            new_page_url = url + "&vjk=" + value1
            #print(new_page_url)
            driver.get(new_page_url)

            wait = WebDriverWait(driver, 25)

            #close annoying popup if it appears
            if driver.find_elements(By.CSS_SELECTOR, "button.popover-x-button-close.icl-CloseButton"):
                #element = WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CLASS_NAME, "popover-x-button-close icl-CloseButton")))
                btn = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "button.popover-x-button-close.icl-CloseButton")))
                btn.click()

            #YOU ARE HERE
            #   current goals is to run SQL query on the text
            #try to access i-frame
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "vjs-container-iframe")))

            #for some reason this fails sometimes, despite increasing the wait time from 10 to 15
            if driver.find_elements(By.ID, "jobDescriptionText"):
                desc_element = driver.find_element_by_id('jobDescriptionText')
                #print(desc_element.text)
                job_post.append(desc_element.text)
                #print("length = " + str(len(desc_element.text)))
                #csv files have a limit of 32,767 characters per cell.
                #no problem, cause description length is like 3000-8000 chars

            else:
                #print('n') #unable to get it. this should be visible on the csv. file.
                job_post.append('--')
            
            driver.switch_to.default_content()

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

            #still within the for loop, append arr containing info of one job post, to a new row in the dataframe
            #each loop, the number is incremented (see line 136)
            sample_df.loc[num] = job_post


    #---outside both for loops, when all jobs scraped for all pages,
    #  save data to csv with relative filepath

    #but first clear the previously made csv file, so that each time the program is run, the results are like new
    filename = "jobs.csv"
    f = open(filename, "w+")
    f.close()


    #now save to csv with relative filepath
    sample_df.to_csv("jobs.csv", encoding='utf-8')

    print('new csv data loaded')

    driver.close()

def main():

    start = perf_counter()

    delete_old_csv()

    sleep(2)

    create_csv()
    #use bucket jobsdatasource
    #use lambda lambda-role-for-jobs-s3-cloudwatch
    #upload_to_bucket() #bucket no longer hosted

    end = perf_counter()
    print("total time (seconds): " + str(end-start)) # float value of time in seconds #roughly 100 seconds for 2 pages
    #use bucket jobsdatasource
    #use lambda lambda-role-for-jobs-s3-cloudwatch
    #upload_to_bucket() #bucket no longer hosted

if __name__ == "__main__":
    main()


# using selenium to work on a dynamically generated webpage

# ->where is the element being clicked?

# iframe id="vjs-container-iframe"
# title="Details of the selected job"

# ->what triggers that iframe to appear?
# presumably, clicking on element with class="cardOutline tapItem"

#https://stackoverflow.com/questions/68419150/python-selenium-how-can-i-get-access-to-this-part-of-the-website

#according to this, you can upgrade your existing bs4 script and don't need to rewrite it
#https://medium.com/ymedialabs-innovation/web-scraping-using-beautiful-soup-and-selenium-for-dynamic-page-2f8ad15efe25

#the inefficent way is just to use html parser on each job card's href
#https://stackoverflow.com/questions/67504953/how-to-get-full-job-descriptions-from-indeed-using-python-and-beautifulsoup

#selenium firefox driver headless?

# selenium click on element
# and then get the description.


#the main objective is to analyze job description data
#record how many hits on software , say, R, pandas, numpy, etc.
#how many hits on langauges, ex: python, C++, etc
#how many hits on years of experience
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

