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
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

# Script for batch creating new CrossRef DOIs from Chalmers CRIS publication records.
# Sample XML: https://gitlab.com/crossref/schema/-/tree/master/best-practice-examples
# Schema: https://crossref.org/schemas/common5.4.0.xsd
# Guide: https://www.crossref.org/documentation/schema-library/markup-guide-metadata-segments/

# CrossRef publication types (supported)
#
# book
# dissertation (both doctoral and lic theses)
# preprint
# report
#

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

# debug
create_doi = True

# Command line params

parser = ArgumentParser(description='Script for creating a new CrossRef DOI from a Chalmers CRIS publication record (semi)manually. Use as (example): python3 create-doi-single.py --pubid "6276a252-7aed-444a-8528-2a4517789c9d" --doi "test.001.aaa" --pubtype report --updateCRIS n -v',
                        formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument("-v", "--verbose", action="store_true", help="increase verbosity")
parser.add_argument("-p", "--pubid", help="Chalmers Research publication ID (long, guid)", required=True)
parser.add_argument("-d", "--doi", help="DOI, without prefix", required=True)
parser.add_argument("-t", "--pubtype", help="Publication type (CrossRef). Allowed values: book, dissertation, preprint, report", required=True)
parser.add_argument("-u", "--updateCRIS", default="y", help="Add the new DOI to the CRIS record (y/n, default:y)", required=True)
args = parser.parse_args()

# Metadata

pubtype = args.pubtype
doi_id = str(doi_prefix) + '/' + args.doi
cris_pubid = args.pubid
update_cris = args.updateCRIS

instname_txt = 'Chalmers University of Technology'
instplace_txt = 'Sweden'
ror_id = 'https://ror.org/040wg7k59'

depositor_name = 'Chalmers Research Support'
depositor_email = 'research.lib@chalmers.se'
cris_updated_by = 'crossref/doi'

# Publ.type specific params

crossref_type = ''
chalmers_publ = 'y'
degree_abbrev = '' # doc or lic?

# Retrieve publication record from Chalmers Research

#cris_query = '_exists_%3AValidatedBy%20%26%26%20PublicationType.Id%3A%22' + str(pubtype_id) + '%22%20%26%26%20!_exists_%3AIdentifierDoi%20%26%26%20CreatedDate%3A%5B2023-06-01%20TO%20*%5D%20%26%26%20DataObjects.IsLocal%3Atrue%20%26%26%20DataObjects.IsMainFulltext%3Atrue%20%26%26%20IsDraft%3Afalse%20%26%26%20IsDeleted%3Afalse%20%26%26%20!_exists_%3AReplacedById%20%26%26%20_exists_%3AIdentifierIsbn&max=' + str(max_records) + '&selectedFields=Id%2CTitle%2CAbstract%2CYear%2CPersons.PersonData.FirstName%2CPersons.PersonData.LastName%2CPersons.PersonData.IdentifierOrcid%2CIncludedPapers%2CLanguage.Iso%2CIdentifierIsbn%2CDispDate%2CSeries%2CKeywords%20%20%20%20'
cris_query = 'Id%3A%22' + str(cris_pubid) + '%22&max=1&selectedFields=Id%2CTitle%2CAbstract%2CYear%2CPersons.PersonData.FirstName%2CPersons.PersonData.LastName%2CPersons.PersonData.IdentifierOrcid%2CIncludedPapers%2CLanguage.Iso%2CIdentifierIsbn%2CDispDate%2CSeries%2CKeywords%2CPersons.Organizations.OrganizationData.Id%2CPersons.Organizations.OrganizationData.OrganizationTypes.NameEng%2CPersons.Organizations.OrganizationData.Country%2CPersons.Organizations.OrganizationData.NameEng%2CPublicationType.NameEng%2CPersons.Organizations.OrganizationData.Identifiers'

research_lookup_url = str(cris_api_ep) + '?query=' + cris_query
research_lookup_headers = {'Accept': 'application/json'}

try:
    research_lookup_data = requests.get(url=research_lookup_url, headers=research_lookup_headers).text
    research_publ = json.loads(research_lookup_data)

    publ = research_publ['Publications'][0]

    if publ:
        print('Found publication ' + str(cris_pubid) + ' in Research.')
        
        # Loop through the pub data and create a new DOI accordingly
        
        # Metadata
        #degree_abbrev = 'PhD'

        xml_filename = ''
        root = ''

        pubid = str(publ['Id'])

        title_txt = publ['Title']
        version_enum = '1'
        year = str(publ['Year'])
        isbn = ''
        isbn_normal = ''
        if 'IdentifierIsbn' in publ:
            if len(publ['IdentifierIsbn']) > 0:
                isbn = str(publ['IdentifierIsbn'][0])
                isbn_normal = isbn.replace('-', '')
                #print(str(isbn_normal ))

        abstract_txt = ''
        if ('Abstract' in publ):
            abstract_txt = publ['Abstract']

        # Persons
        authors = []
        authors = publ['Persons']
        
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
        create_date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        runtime_date = datetime.datetime.now().strftime("%Y-%m-%d:%H:%M:%S")

        # Clean relevant text fields
        abstract_clean = ''
        if abstract_txt:
            abstract_clean = BeautifulSoup(abstract_txt.rstrip('\r\n').strip(), "lxml").text

        if title_txt:
            title_clean = BeautifulSoup(title_txt.rstrip('\r\n').strip(), "lxml").text

        print('\nDOI: ' + doi_id + '\nTitle: ' + title_txt + '\nResearch Pubtype: ' + str(publ['PublicationType']['NameEng']) + '\nCrossRef Pubtype: ' + pubtype + '\nResearch ID: ' + cris_pubid + '\nUpdate Research?: ' + update_cris + '\n\nShould we create a DOI for this? (y/n)')
        yes = {'yes', 'y', 'ye', 'j', 'ja', ''}
        no = {'no', 'n', 'nej'}
        choice = input().lower()
        if choice in yes:
            print('Ok')
            # continue
        elif choice in no:
            print('Ok, exiting...')
            exit()

        # Write to log
        with open(logfile, 'a') as lfile:
            lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tTrying to create a new DOI: ' + doi_id + ' for Research publ: ' + cris_url + '\n')
            lfile.close()

            # Create XML file

            schema = "http://www.crossref.org/schema/5.4.0 https://www.crossref.org/schemas/crossref5.4.0.xsd"
            namespace = "http://www.crossref.org/schema/5.4.0"
            version = "5.4.0"

            xml_filename = create_date + '.xml'

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
            if pubtype == 'dissertation':
                publication = ET.SubElement(body, pubtype, publication_type="full_text", language=lang)
            if pubtype == 'book':
                publication_book = ET.SubElement(body, pubtype, book_type="monograph")
                publication = ET.SubElement(publication_book, "book_metadata", language=lang)
            if pubtype == 'preprint':
                publication = ET.SubElement(body, "posted_content", type=pubtype)
            if pubtype == 'report':
                publication_report = ET.SubElement(body, "report-paper")
                publication = ET.SubElement(publication_report, "report-paper_metadata", language=lang)        
            contributors = ET.SubElement(publication, "contributors")
            if authors:
                for a in authors:
                    person_name = ET.SubElement(contributors, "person_name", contributor_role="author")
                    ET.SubElement(person_name, "given_name").text = a['PersonData']['FirstName']
                    ET.SubElement(person_name, "surname").text = a['PersonData']['LastName']
                    if 'IdentifierOrcid' in a['PersonData']:
                         if len(a['PersonData']['IdentifierOrcid']) > 0:
                            orcid = ET.SubElement(person_name, "ORCID", authenticated = "True").text = str(a['PersonData']['IdentifierOrcid'][0])  
                    affiliations = ET.SubElement(person_name, "affiliations")
                    for aff in a['Organizations']:
                        institution = ET.SubElement(affiliations, "institution")
                        if str(aff['OrganizationData']['OrganizationTypes'][0]['NameEng']).startswith('Chalmers'):
                            ror = ET.SubElement(institution, "institution_id", type="ror").text = ror_id
                            instname = ET.SubElement(institution, "institution_name").text = instname_txt
                            instplace = ET.SubElement(institution, "institution_place").text = instplace_txt
                        else:
                            instname = ET.SubElement(institution, "institution_name").text = aff['OrganizationData']['NameEng']
                            instplace = ET.SubElement(institution, "institution_place").text = aff['OrganizationData']['Country']
                        for orgid in aff['OrganizationData']['Identifiers']:
                            if orgid['Type']['Value'] == 'ROR_ID':
                                ror = ET.SubElement(institution, "institution_id", type="ror").text = str(orgid['Value'])      

            titles = ET.SubElement(publication, "titles")
            title = ET.SubElement(titles, "title").text = title_clean
            if pubtype == 'dissertation':
                if disp_date:
                    if len(disp_date) > 0:
                        approvaldate = ET.SubElement(publication, "approval_date")
                        aday = ET.SubElement(approvaldate, "day").text = disp_date[8:10]
                        amonth = ET.SubElement(approvaldate, "month").text = disp_date[5:7]
                        ayear = ET.SubElement(approvaldate, "year").text = disp_date[0:4]
            if pubtype == 'dissertation':
                institution_publ = ET.SubElement(publication, "institution")
                ror_publ = ET.SubElement(institution_publ, "institution_id", type="ror").text = ror_id
                instname_publ = ET.SubElement(institution_publ, "institution_name", language=lang).text = instname_txt
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
            if chalmers_publ:
                publisher = ET.SubElement(publication, "publisher").text = instname_txt
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

            print('Attempting to create a DOI: ' + doi_id + ' for Research publ: ' + cris_url + ' using file: ' + xml_filename)

            if create_doi == True:
         
                files = {
                        'operation': (None, 'doQueryUpload'),
                        'login_id': (None, crossref_uid),
                        'login_passwd': (None, crossref_pw),
                        'fname': ('[filename]', open(xml_filename, 'rb'))
                }

                try:
                    response = requests.post(crossref_ep, files=files)
                    if response.status_code == 401:
                        print("Something went wrong! Response: " + str(response.reason))
                        with open(logfile, 'a') as lfile:
                            lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tCreating DOI: ' + doi_id + ' for Research publ: ' + cris_url + ' using file: ' + xml_filename + ' failed! Response: ' + str(response.reason) + '\n\n')
                            lfile.close()
                        exit()
                    else:
                        print("DOI was created. Status: " + str(response.status_code))
                except requests.exceptions.HTTPError as e:
                    print('DOI was not created, exiting now. Exception: ' + str(e))
                    with open(logfile, 'a') as lfile:
                            lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tDOI could NOT be created: ' + doi_id + ' for Research publ: ' + cris_url + ' using file: ' + xml_filename + '\n\n')
                            lfile.close()
                    exit()
                
                if update_cris == 'y':
                    # Update publication record in Research (if ok)
                    research_url = str(cris_api_ep) + cris_pubid
                    research_headers = {'Accept': 'application/json'}
                    print('Updating publication ID: ' + cris_pubid + ' in Research.')
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
                        print('Something went wrong! Exiting.')
                        exit()
                else:
                    print('Chalmers CRIS publication was NOT updated! Use -u y to do this.')  

                # Write to log end exit
                with open(logfile, 'a') as lfile:
                    lfile.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '\tCreated DOI: ' + doi_id + ' for Research publ: ' + cris_url + '. Filename: ' + xml_filename + '\n')
                    lfile.close()

                # Write runtime timestamp to file (only if all has finished without issues)
                with open(runtime_file, 'w') as rtfile:
                    rtfile.write(runtime_date + '\n')
                    rtfile.close()
            else:
                print('DOI was NOT created, due to system settings.')
        #sleep(10)

        # debug
        #exit()
    else:
        print('No publs found, exiting!')
        exit()

except requests.exceptions.HTTPError as e:
    print("A general error occured! Exiting.")
    exit()

# finish here
exit()
