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

# Use as (example): python3 create-doi-single.py --pubid "6276a252-7aed-444a-8528-2a4517789c9d" --doi "test.001.aaa" --pubtype report --updateCRIS y -v

# CrossRef publication types (supported)
#
# book
# dissertation (both doctoral and lic theses)
# preprint
# proceeding (single)
# report
#

m_encoding = 'UTF-8'

# Params
load_dotenv()
crossref_ep = os.getenv("CROSSREF_API_EP")
crossref_uid = os.getenv("CROSSREF_UID")
crossref_pw = os.getenv("CROSSREF_PW")
schema_version = os.getenv("SCHEMA_VERSION")
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

parser = ArgumentParser(description='Script for creating a new CrossRef DOI from a Chalmers CRIS publication record (semi)manually. \nUse as (example): python3 create-doi-single.py --pubid "6276a252-7aed-444a-8528-2a4517789c9d" --doi "test.001.aaa" --pubtype report --updateCRIS y -v',
                        formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument("-v", "--verbose", action="store_true", help="increase verbosity")
parser.add_argument("-p", "--pubid", help="Chalmers Research publication ID (long, guid)", required=True)
parser.add_argument("-d", "--doi", help="DOI, without prefix", required=True)
parser.add_argument("-t", "--pubtype", help="Publication type (CrossRef). Allowed values: book, dissertation, preprint, proceeding, report", required=True)
parser.add_argument("-u", "--updateCRIS", default="y", help="Add the new DOI to the CRIS record (y/n)")
args = parser.parse_args()

# Metadata

pubtype = args.pubtype
doi_id = str(doi_prefix) + '/' + args.doi
cris_pubid = args.pubid
update_cris = args.updateCRIS

# Validate input
if pubtype not in ['book','dissertation','preprint','proceeding','report']:
    print('ERROR: Pubtype has to be one of "book", "dissertation", "preprint", "proceeding","report"')
    exit()

if update_cris not in ['y','n']:
    print('ERROR! UpdateCRIS (-u) has to be y(es) or n(no), default yes (if empty)')
    exit()

if str(args.doi).startswith('10.63959'):
    print('ERROR: DOI should be WITHOUT prefix!')
    exit()

if len(cris_pubid) < 12:
    print('ERROR: Publication ID should be the long (guid) id!')
    exit()

instname_txt = 'Chalmers University of Technology'
instplace_txt = 'Gothenburg, Sweden'
ror_id = 'https://ror.org/040wg7k59'

depositor_name = 'Chalmers Research Support'
depositor_email = 'research.lib@chalmers.se'
cris_updated_by = 'crossref/doi'

# Publ.type specific params

crossref_type = ''
chalmers_publ = 'y'
degree_abbrev = '' # doc or lic?

# Retrieve publication record from Chalmers Research

cris_query = 'Id%3A%22' + str(cris_pubid) + '%22&max=1&selectedFields=Id%2CTitle%2CAbstract%2CYear%2CPersons.PersonData.FirstName%2CPersons.PersonData.LastName%2CPersons.PersonData.IdentifierOrcid%2CIncludedPapers%2CLanguage.Iso%2CConference%2CIdentifierIsbn%2CIdentifierDoi%2CDispDate%2CSeries%2CKeywords%2CPersons.Organizations.OrganizationData.Id%2CPersons.Organizations.OrganizationData.OrganizationTypes.NameEng%2CPersons.Organizations.OrganizationData.Country%2CPersons.Organizations.OrganizationData.City%2CPersons.Organizations.OrganizationData.NameEng%2CPublicationType.NameEng%2CPersons.Organizations.OrganizationData.Identifiers'

research_lookup_url = str(cris_api_ep) + '?query=' + cris_query
research_lookup_headers = {'Accept': 'application/json'}

try:
    research_lookup_data = requests.get(url=research_lookup_url, headers=research_lookup_headers).text
    research_publ = json.loads(research_lookup_data)

    publ = ''
    if 'Publications' in research_publ:
        if len(research_publ['Publications']) > 0:
            publ = research_publ['Publications'][0]
    else:
        print('ERROR! No Research publication found for id ' + cris_pubid + ', exiting!')
        exit()

    if publ:
        print('Found publication ' + str(cris_pubid) + ' in Research.')
        
        # Loop through the pub data and create a new DOI accordingly
        
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

        conference = []
        if 'Conference' in publ:
            if len(publ['Conference']) > 0:
                conference = publ['Conference']
        
        # Check if item already has a DOI (just in case)
        if 'IdentifierDoi' in publ:
            if len(publ['IdentifierDoi']) > 0 and update_cris == 'y':
                print('\nIt seems this item already has a DOI in Research:  ' + str(publ['IdentifierDoi'][0]) + '\nIs this correct? Do you wish to continue (this would add a possible duplicate)? (y/n)')
                yes = {'yes', 'y', 'ye', 'j', 'ja', ''}
                no = {'no', 'n', 'nej'}
                choice = input().lower()
                if choice in yes:
                    print('Ok')
                    # continue
                elif choice in no:
                    print('Ok, exiting...')
                    exit()

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
                        #print(pubinc)
                        if 'IdentifierDoi' in pubinc:
                            if len(pubinc['IdentifierDoi']) > 0:
                                included_paper_dois.append(str(pubinc['IdentifierDoi'][0]))

        lang = publ['Language']['Iso']
        
        cris_pubtype = publ['PublicationType']['NameEng']

        if cris_pubtype == 'Doctoral thesis':
            degree_abbrev = 'PhD'
        if cris_pubtype == 'Licentiate thesis':
            degree_abbrev = 'Licentiate'

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

        print('\nITEM DETAILS\n============\nNew DOI: ' + doi_id + '\nTitle: ' + title_txt + '\nResearch Pubtype: ' + cris_pubtype + '\nCrossRef Pubtype: ' + pubtype + '\nResearch ID: ' + cris_pubid + '\nUpdate Research?: ' + update_cris + '\n\nShould we create a DOI for this? (y/n)')
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

            schema = "http://www.crossref.org/schema/" + str(schema_version) + " https://www.crossref.org/schemas/crossref" + schema_version + ".xsd"
            namespace = "http://www.crossref.org/schema/" + str(schema_version)
            version = schema_version

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
                                {attr_qname: "http://www.crossref.org/schema/" + str(schema_version) + " https://www.crossref.org/schemas/crossref" + str(schema_version) + ".xsd"},
                                xmlns='http://www.crossref.org/schema/' + schema_version +'',
                                version=schema_version)
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
            if pubtype == 'proceeding':
                publication_proc = ET.SubElement(body, "conference")
            if pubtype == 'proceeding':
                contributors = ET.SubElement(publication_proc, "contributors")
            else:
                contributors = ET.SubElement(publication, "contributors")
            if authors:
                seq = 0
                seq_txt = 'first'
                for a in authors:
                    role = 'author'
                    if pubtype == 'proceeding':
                        role = 'editor'
                    if seq == 0:
                        seq_txt = 'first'
                    else:
                        seq_txt = 'additional'
                    person_name = ET.SubElement(contributors, "person_name", contributor_role=role, sequence=seq_txt)
                    ET.SubElement(person_name, "given_name").text = a['PersonData']['FirstName']
                    ET.SubElement(person_name, "surname").text = a['PersonData']['LastName']
                    affiliations = ET.SubElement(person_name, "affiliations")
                    for aff in a['Organizations']:
                        institution = ET.SubElement(affiliations, "institution")
                        if str(aff['OrganizationData']['OrganizationTypes'][0]['NameEng']).startswith('Chalmers'):
                            if pubtype in ['dissertation','report','book','preprint']:
                                instname = ET.SubElement(institution, "institution_name").text = instname_txt
                            ror = ET.SubElement(institution, "institution_id", type="ror").text = ror_id
                        else:
                            if pubtype in ['dissertation','report','book','preprint']:
                                instname = ET.SubElement(institution, "institution_name").text = aff['OrganizationData']['NameEng']
                            else:
                                instname = ET.SubElement(institution, "institution_acronym").text = aff['OrganizationData']['NameEng']
                        for orgid in aff['OrganizationData']['Identifiers']:
                            if orgid['Type']['Value'] == 'ROR_ID':
                                ror = ET.SubElement(institution, "institution_id", type="ror").text = str(orgid['Value'])
                        if 'City' in aff['OrganizationData']:
                            instplace = ET.SubElement(institution, "institution_place").text = str(aff['OrganizationData']['City']) + ', ' + str(aff['OrganizationData']['Country'])
                        else:    
                            instplace = ET.SubElement(institution, "institution_place").text = str(aff['OrganizationData']['Country'])
                    if 'IdentifierOrcid' in a['PersonData']:
                         if len(a['PersonData']['IdentifierOrcid']) > 0:
                            orcid = ET.SubElement(person_name, "ORCID", authenticated = "true").text = "https://orcid.org/" + str(a['PersonData']['IdentifierOrcid'][0])  
                    seq += 1
            if pubtype == 'proceeding':
                if conference:
                    event = ET.SubElement(publication_proc, "event_metadata")
                    event_name = ET.SubElement(event, "conference_name").text = conference['Name']
                    if 'City' in conference:
                        if 'Country' in conference:
                            event_place = ET.SubElement(event, "conference_location").text = str(conference['City']) + ', ' + str(conference['Country']['NameEng'])
                    if 'StartDate' in conference:
                        if 'EndDate' in conference:
                            startdate = str(conference['StartDate'])
                            enddate = str(conference['EndDate'])
                            event_dates = ET.SubElement(event, "conference_date", start_month=startdate[5:7], start_year=startdate[0:4], start_day=startdate[8:10], end_month=enddate[5:7], end_year=enddate[0:4], end_day=enddate[8:10])
                publication = ET.SubElement(publication_proc, "proceedings_metadata", language=lang)
                proceedings_title = ET.SubElement(publication, "proceedings_title").text = title_clean       
            if pubtype in ['book', 'dissertation', 'preprint', 'report']:
                titles = ET.SubElement(publication, "titles")
                title = ET.SubElement(titles, "title").text = title_clean
            if pubtype in ['preprint']:
                posted_date = ET.SubElement(publication, "posted_date")
                posted_year = ET.SubElement(posted_date, "year").text = year
            if abstract_clean and pubtype in ['book', 'dissertation', 'preprint', 'report']:
                abstract = ET.SubElement(publication, ET.QName(ns_map["jats"], "abstract"))
                abstract_p = ET.SubElement(abstract, ET.QName(ns_map["jats"], "p")).text = abstract_clean
            if pubtype == 'dissertation':
                if disp_date:
                    if len(disp_date) > 0:
                        approvaldate = ET.SubElement(publication, "approval_date")
                        amonth = ET.SubElement(approvaldate, "month").text = disp_date[5:7]
                        aday = ET.SubElement(approvaldate, "day").text = disp_date[8:10]
                        ayear = ET.SubElement(approvaldate, "year").text = disp_date[0:4]
            if pubtype == 'dissertation':
                institution_publ = ET.SubElement(publication, "institution")
                ror_publ = ET.SubElement(institution_publ, "institution_id", type="ror").text = ror_id
            if degree_abbrev:
                degree = ET.SubElement(publication, "degree").text = degree_abbrev
            if chalmers_publ and pubtype in ['proceeding']:
                publisher = ET.SubElement(publication, "publisher")
                publisher_name = ET.SubElement(publisher, "publisher_name").text = instname_txt
                publisher_place = ET.SubElement(publisher, "publisher_place").text = instplace_txt
            if pubtype in ['report','book','proceeding']:
                pubdate = ET.SubElement(publication, "publication_date", media_type = "online")
                pubyear = ET.SubElement(pubdate, "year").text = year
            if isbn:
                isbn_print = ET.SubElement(publication, "isbn").text = isbn
            else:
                if pubtype in ['proceeding','book']:
                    isbn_print = ET.SubElement(publication, "noisbn", reason='monograph')
            if chalmers_publ and pubtype in ['report','book']:
                publisher = ET.SubElement(publication, "publisher")
                publisher_name = ET.SubElement(publisher, "publisher_name").text = instname_txt
                publisher_place = ET.SubElement(publisher, "publisher_place").text = instplace_txt
            # Adding included papers as relations is currently not supported...
            #if included_paper_dois:
            #    related_ids = ET.SubElement(publication, "relatedIdentifiers")
            #    for incl_doi in included_paper_dois:
            #        related_doi = ET.SubElement(related_ids, "relatedIdentifier", relatedIdentifierType="DOI", relationType="HasPart").text = incl_doi.strip()
            if pubtype in ['dissertation','report','preprint']:
                version_info = ET.SubElement(publication, "version_info")
                version = ET.SubElement(version_info, "version").text = version_enum
            doi_data = ET.SubElement(publication, "doi_data")
            doi = ET.SubElement(doi_data, "doi").text = doi_id
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
                        'operation': (None, 'doMDUpload'),
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
        print('ERROR! No Research publication found for id ' + cris_pubid + ', exiting!')
        exit()

except requests.exceptions.HTTPError as e:
    print("A general error occured! Exiting.")
    exit()

# finish here
exit()
