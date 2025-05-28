#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import xml.dom.minidom
import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import json
from time import sleep

# Script for batch creating new CrossRef DOIs from Chalmers CRIS publication records.
# Sample XML: https://gitlab.com/crossref/schema/-/blob/master/best-practice-examples/dissertation.5.4.0.xml
# Schema: https://crossref.org/schemas/common5.4.0.xsd
# Guide: https://www.crossref.org/documentation/schema-library/markup-guide-metadata-segments/

m_encoding = 'UTF-8'

# Params
load_dotenv()
crossref_ep = os.getenv("CROSSREF_API_EP")
crossref_uid = os.getenv("CROSSREF_UID")
crossref_pw = os.getenv("CROSSREF_PW")
logfile = os.getenv("LOGFILE")
runtime_file = os.getenv("RUNTIME")
create_doi = os.getenv("CREATE_DOI")
doi_prefix = os.getenv("DOI_PREFIX")
cris_base_url = os.getenv("CRIS_BASE_URL")
cris_api_ep = os.getenv("CRIS_API_EP")
pubtype_id = os.getenv("PUBTYPE_ID")
max_records = os.getenv("MAXRECORDS")

instname_txt = 'Chalmers University of Technology'
instplace_txt = 'Gothenburg, Sweden'
ror_id = 'https://ror.org/040wg7k59'

depositor_name = 'Chalmers Research Support'
depositor_email = 'research.lib@chalmers.se'
cris_updated_by = 'crossref/doi'

# Retrieve publication records from Chalmers Research

# IsValidated:true
# IsDraft:false
# IsDeleted:false
# ReplacedById:null
# CreatedDate:[from to *]
# PublicationType.Id:645ba094-942d-400a-84cc-ec47ee01ec48 (doc thesis)
# IdentifierDoi:null
# IdentifierIsbn:not null
# DataObjects:not null
# IsLocal:true
# IsMainFulltext:true

cris_query = '_exists_%3AValidatedBy%20%26%26%20PublicationType.Id%3A%22' + str(pubtype_id) + '%22%20%26%26%20!_exists_%3AIdentifierDoi%20%26%26%20CreatedDate%3A%5B2023-06-01%20TO%20*%5D%20%26%26%20DataObjects.IsLocal%3Atrue%20%26%26%20DataObjects.IsMainFulltext%3Atrue%20%26%26%20IsDraft%3Afalse%20%26%26%20IsDeleted%3Afalse%20%26%26%20!_exists_%3AReplacedById%20%26%26%20_exists_%3AIdentifierIsbn&max=' + str(max_records) + '&selectedFields=Id%2CTitle%2CAbstract%2CYear%2CPersons.PersonData.FirstName%2CPersons.PersonData.LastName%2CPersons.PersonData.IdentifierOrcid%2CIncludedPapers%2CLanguage.Iso%2CIdentifierIsbn%2CDispDate%2CSeries%2CKeywords%20%20%20%20'

research_lookup_url = str(cris_api_ep) + '?query=' + cris_query
research_lookup_headers = {'Accept': 'application/json'}

try:
    research_lookup_data = requests.get(url=research_lookup_url, headers=research_lookup_headers).text
    research_publs = json.loads(research_lookup_data)

    if research_publs['TotalCount'] > 0:
        print('Found publs: ' + str(research_publs['TotalCount']))
        
        # Loop through and create new DOI:s accordingly
        
        # Metadata
        pubtype = 'dissertation'
        degree_abbrev = 'PhD'

        for publ in research_publs['Publications']:

            xml_filename = ''
            root = ''

            pubid = str(publ['Id'])
            print(str(pubid ))

            title_txt = publ['Title']
            version_enum = '1'
            year = str(publ['Year'])
            isbn = str(publ['IdentifierIsbn'][0])
            isbn_normal = isbn.replace('-', '')
            print(str(isbn_normal ))

            abstract_txt = ''
            if ('Abstract' in publ):
                abstract_txt = publ['Abstract']

            # Only use first person (should only be 1)
            author = publ['Persons'][0]['PersonData']
            author_fname = author['FirstName']
            author_lname = author['LastName']
            orcid_txt = ''
            if 'IdentifierOrcid' in author:
                if len(author['IdentifierOrcid']) > 0:
                    orcid_txt = str(author['IdentifierOrcid'][0])

            included_paper_dois = []
            if ('IncludedPapers') in publ:
                if len(publ['IncludedPapers']) > 0:
                    for inclp in publ['IncludedPapers']:
                        # Retrieve DOI from inluded papers and add these
                        incl_pubid = str(inclp['Publication'])
                        incl_doi_request_url = str(cris_api_ep) + '?query=Id%3A%22' + incl_pubid + '%22&selectedFields=Id%2CIdentifierDoi'
                        incl_doi_request_headers = {'Accept': 'application/json'}
                        incl_doi_request_data = requests.get(url=incl_doi_request_url, headers=incl_doi_request_headers).text
                        incl_doi_request_publs = json.loads(incl_doi_request_data)
                        pubinc = incl_doi_request_publs['Publications'][0]
                        print(pubinc)
                        if 'IdentifierDoi' in pubinc:
                            if len(pubinc['IdentifierDoi']) > 0:
                                included_paper_dois.append(str(pubinc['IdentifierDoi'][0]))

            lang = publ['Language']['Iso']

            disp_date = ''
            if 'DispDate' in publ:
                disp_date = str(publ['DispDate'])

            itemnumber = ''
            if 'Series' in publ:
                if len(publ['Series']) > 0:
                    for serie in publ['Series']:
                        if  serie['SerialItem']['Id'] == '3b982ea2-6c34-1014-b6a7-7ac9b7ba4313':
                            itemnumber = str(serie['SerialNumber'])
                    
            cris_pubid = pubid
            cris_url = str(cris_base_url) + cris_pubid
            doi_id = str(doi_prefix) + '/' + isbn_normal
            create_date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            runtime_date = datetime.datetime.now().strftime("%Y-%m-%d:%H:%M:%S")

            # Clean relevant text fields
            if abstract_txt:
                abstract_clean = BeautifulSoup(abstract_txt.rstrip('\r\n').strip(), "lxml").text

            if title_txt:
                title_clean = BeautifulSoup(title_txt.rstrip('\r\n').strip(), "lxml").text

            # Write to log
            with open(logfile, 'a') as lfile:
                lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tTrying to create a new DOI: ' + doi_id + ' for Research publ: ' + cris_url + '\n')
                lfile.close()

            # Create XML file

            schema = "http://www.crossref.org/schema/5.4.0 https://www.crossref.org/schemas/crossref5.4.0.xsd"
            namespace = "http://www.crossref.org/schema/5.4.0"
            version = "5.4.0"

            xml_filename = isbn_normal + '.xml'

            ns = namespace
            xsi = "http://www.w3.org/2001/XMLSchema-instance" 
            jats = "http://www.ncbi.nlm.nih.gov/JATS1"
            mml = "http://www.w3.org/1998/Math/MathML"
            fr = "http://www.crossref.org/fundref.xsd"

            attr_qname = ET.QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
            ns_map = { "jats": jats,"mml": mml,"xsi": xsi,"fr": fr }

            for prefix, uri in ns_map.items():
                ET.register_namespace(prefix, uri)

            root = ET.Element("doi_batch", 
                                {attr_qname: "http://www.crossref.org/schema/5.4.0 https://www.crossref.org/schemas/crossref5.4.0.xsd"},
                                version=version)

            #root = ET.Element(ET.QName(ns_map["xsi"], "doi_batch"))

            head = ET.SubElement(root, "head")
            ET.SubElement(head, "doi_batch_id").text = doi_id
            ET.SubElement(head, "timestamp").text = create_date
            depositor = ET.SubElement(head, "depositor")
            ET.SubElement(depositor, "depositor_name").text = depositor_name
            ET.SubElement(depositor, "email_address").text = depositor_email
            ET.SubElement(head, "registrant").text = instname_txt
            body = ET.SubElement(root, "body")
            publication = ET.SubElement(body, pubtype, publication_type="full_text", language=lang)
            contributors = ET.SubElement(publication, "contributors")
            person_name = ET.SubElement(contributors, "person_name", sequence="first", contributor_role="author")
            ET.SubElement(person_name, "given_name").text = author_fname
            ET.SubElement(person_name, "surname").text = author_lname
            if orcid_txt:
                orcid = ET.SubElement(person_name, "ORCID", authenticated = "True").text = orcid_txt
            affiliations = ET.SubElement(person_name, "affiliations")
            institution = ET.SubElement(affiliations, "institution")
            ror = ET.SubElement(institution, "institution_id", type="ror").text = ror_id
            instname = ET.SubElement(institution, "institution_name").text = instname_txt
            instplace = ET.SubElement(institution, "institution_place").text = instplace_txt
            titles = ET.SubElement(publication, "titles")
            title = ET.SubElement(titles, "title").text = title_clean
            if disp_date:
                approvaldate = ET.SubElement(publication, "approval_date")
                aday = ET.SubElement(approvaldate, "day").text = disp_date[8:10]
                amonth = ET.SubElement(approvaldate, "month").text = disp_date[5:7]
                ayear = ET.SubElement(approvaldate, "year").text = disp_date[0:4]
            institution_publ = ET.SubElement(publication, "institution")
            ror_publ = ET.SubElement(institution_publ, "institution_id", type="ror").text = ror_id
            instname_publ = ET.SubElement(institution_publ, "institution_name", language=lang).text = instname
            if degree_abbrev:
                degree = ET.SubElement(publication, "degree").text = degree_abbrev
            version = ET.SubElement(publication, "version")
            version_info = ET.SubElement(version, "version_info").text = version_enum
            if abstract_clean:
                abstract = ET.SubElement(publication, ET.QName(ns_map["jats"], "abstract"))
                abstract_p = ET.SubElement(abstract, ET.QName(ns_map["jats"], "p")).text = abstract_clean
            pubdate = ET.SubElement(publication, "publication_date", media_print = "print").text = year
            if itemnumber:
                itemnumber = ET.SubElement(publication, "item_number", type = "institution").text = itemnumber
            if isbn:
                isbn_print = ET.SubElement(publication, "isbn", media_type="print").text = isbn
            publisher = ET.SubElement(publication, "publisher").text = instname
            if included_paper_dois:
                related_ids = ET.SubElement(publication, "relatedIdentifiers")
                for incl_doi in included_paper_dois:
                    related_doi = ET.SubElement(related_ids, "relatedIdentifier", relatedIdentifierType="DOI", relationType="HasPart").text = incl_doi.strip()
            doi_data = ET.SubElement(publication, "doi_data")
            doi = ET.SubElement(doi_data, "doi_data").text = doi_id
            resource = ET.SubElement(doi_data, "resource").text = cris_url

            # Create file
            dom = xml.dom.minidom.parseString(ET.tostring(root))
            xml_string = dom.toprettyxml()
            part1, part2 = xml_string.split('?>')

            with open(xml_filename, 'w') as xfile:
                xfile.write(part1 + 'encoding=\"{}\"?>'.format(m_encoding) + part2)
                xfile.close()
            
            # Post XML to CrossRef endpoint
            # https://www.crossref.org/documentation/register-maintain-records/direct-deposit-xml/https-post/

            if create_doi:
                    
                files = {
                        'operation': (None, 'doQueryUpload'),
                        'login_id': (None, crossref_uid),
                        'login_passwd': (None, crossref_pw),
                        'fname': ('[filename]', open(xml_filename, 'rb'))
                }

                print('Creating DOI: ' + doi_id + ' for Research publ: ' + cris_url + ' using file: ' + xml_filename + '\n')

                try:
                    response = requests.post(crossref_ep, files=files)
                    if response.status_code == 401:
                        print("Something went wrong. Response: " + str(response.reason))
                        with open(logfile, 'a') as lfile:
                            lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tCreating DOI: ' + doi_id + ' for Research publ: ' + cris_url + ' using file: ' + xml_filename + ' failed! Response: ' + str(response.reason) + '\n\n')
                            lfile.close()
                        #exit()
                        continue
                    else:
                        print("DOI was created. Status: " + str(response.status_code))
                except requests.exceptions.HTTPError as e:
                    print('DOI was not created, exiting now. Exception: ' + str(e))
                    with open(logfile, 'a') as lfile:
                            lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tDOI could NOT be created: ' + doi_id + ' for Research publ: ' + cris_url + ' using file: ' + xml_filename + '\n\n')
                            lfile.close()
                    #exit()
                    continue
                
                # Update publication record in Research (if ok)
                print('Updating publication ID: ' + cris_pubid + ' in Research.')
                research_url = str(cris_api_ep) + cris_pubid
                research_headers = {'Accept': 'application/json'}

                try:
                    research_data = requests.get(url=research_url, headers=research_headers).text
                    # Read response and add updated info
                    datestring = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
                    research_publ = json.loads(research_data)
                    research_publ['UpdatedBy'] = cris_updated_by
                    research_publ['UpdatedDate'] = datestring

                    new_doi = {}
                    new_doi_type = {}
                    new_doi_type['Id'] = '5907253f-7ad4-4b1e-84d1-7e72ea1d92a8'
                    new_doi['Type'] = new_doi_type
                    new_doi['CreatedBy'] = cris_updated_by
                    new_doi['CreatedAt'] = datestring
                    new_doi['Value'] = doi_id

                    existing_ids = research_publ['Identifiers']
                    new_ids = {}
                    new_ids = existing_ids
                    existing_ids.append(new_doi)

                    research_publ['Identifiers'] = new_ids

                    updated_record = json.dumps(research_publ)

                    try:
                        print('Updating record: ' + cris_pubid + ' in Research\n')
                        response = requests.put(research_url, json=json.loads(updated_record), headers=research_headers)
                        if response.status_code == 200:
                            print(cris_pubid + ' UPDATED\n')
                            with open(logfile, 'a') as lfile:
                                lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tResearch CRIS publication ' + cris_pubid + ' has been updated!\n')
                                lfile.close()
                        else:
                            print(cris_pubid + ' could not be updated! ' + 'Status: ' + str(response.status_code) + '\n')
                            with open(logfile, 'a') as lfile:
                                lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tResearch CRIS publication ' + cris_pubid + ' count NOT be updated!\n')
                                lfile.close()
                    except requests.exceptions.HTTPError as e:
                        print('Exception.')
                        with open(logfile, 'a') as lfile:
                                lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tResearch CRIS publication ' + cris_pubid + ' count NOT be updated!\n')
                                lfile.close()
                        print('\n')

                except requests.exceptions.HTTPError as e:
                    print('Exception.')   

            # Write to log end exit
            with open(logfile, 'a') as lfile:
                lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tCreated DOI: ' + doi_id + ' for Research publ: ' + cris_url + '. Filename: ' + xml_filename + '\n')
                lfile.close()

            # Write runtime timestamp to file (only if all has finished without issues)
            with open(runtime_file, 'w') as rtfile:
                rtfile.write(runtime_date + '\n')
                rtfile.close()

        sleep(10)

        # debug
        #exit()
    else:
        print('No publs found, exiting!')
        exit()

except requests.exceptions.HTTPError as e:
    print("error")
    exit()

# finish here
exit()
