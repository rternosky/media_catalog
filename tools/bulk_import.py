#!/usr/bin/env python
"""
Copyright 2018 Robert Ternosky

  Import book data from a CSV file, fetch more data from OpenLibrary.org
  and populate data into the Media Catalog database.

  REQUIRED: File must contain a column called "ISBN".
  Extra columns can be used to augment missing data for OpenLibrary.org

  Example import format will look like this if using the Android App
  "My Library" to scan ISBN codes:

    Title,Authors,Series,Categories,Published date,Publisher,Pages,ISBN,
    Read,Reading periods,Comments,Summary,Cover path
"""
import argparse
import csv
import datetime
import os
import pprint

import requests

DEFAULT_BASE_URL = 'https://openlibrary.org/api/books'

def build_query_string(isbn_list):
    """Build up URL for OpenLibrary.org search using a list of ISBN numbers.

    :param isbn_list: List of Strings. List of ISBN string values.
    :returns: String. URL to fetch books by ISBN

    :precondition: isbn_list is list of strings in ISBN format
    """
    assert isinstance(isbn_list, (list, tuple))

    query = ['jscmd=data', 'format=json']
    isbns = []
    for isbn in isbn_list:
        isbns.append('ISBN:{}'.format(isbn))
    query.append('bibkeys={}'.format(','.join(isbns)))
    return "{}?{}".format(DEFAULT_BASE_URL, '&'.join(sorted(query)))

def search_isbn(isbn_list):
    """Search OpenLibrary.org for books using a list of ISBN numbers.

    :param isbn_list: List of Strings. List of ISBN string values.
    :returns: Dictionary. { ISBN: {info from openlibrary} }
    :raises requests.exceptions.HTTPError on failure
    :precondition: isbn_list is list of strings in ISBN format
    """
    assert isinstance(isbn_list, (list, tuple))

    full_url = build_query_string(isbn_list=isbn_list)
    resp = requests.get(full_url)
    resp.raise_for_status()
    return resp.json()

def build_arg_parser():
    """Build an argpare.ArgumentParser() object

    :returns: argparse.ArgumentParser()
    """
    parser = argparse.ArgumentParser(description='Import books into database from CSV')

    # Positional Arguments
    parser.add_argument('fname', action='store', help='CSV filename to use as input')

    # Named arguments, i.e. starting with "-" or "--"
    parser.add_argument('-C', '--commit', dest='commit', action='store_true', required=False,
                        default=False, help='Commit database work? (default: no)')
    parser.add_argument('-v', '--verbose', dest='verbose', action='count', required=False,
                        default=0, help='Increase verbosity level (default: 0)')
    return parser

def validate_args(parser):
    """Validate command line arguments

    :param parser: argparse.ArgumentParser()
    :returns: argparse.Namespace() object
    :raises: SystemExit on fatal issues
    """
    args = parser.parse_args()
    if not os.path.exists(args.fname):
        parser.error('filename : {} does not exist or cannot be reached'.format(args.fname))

    return args

def process_book(csv_book, ol_book):
    """Process a book and write to database.

    :param csv_book: Dictionary. Row from CSV file representing a book
    :param ol_book: Dictionary. Data from Open Library for ISBN from csv_book
    """
    # XXX: 2 sets of data. Use command line flags to control which takes precedence
    # CSV data:
    #   authors: '...' (seems to be same format as OL
    #   comments: ''
    #   isbn: ''
    #   pages: '#'
    #   published date: 'DD/MM/YYYY'
    #   publisher: ''
    #   series: ''
    #   summary: ''
    #   title: ''

    # OL data:
    #   authors: [ {name, url}, ..]
    #   cover: { large, medium, small }
    #   identifiers: {goodreads: ['', ... ], isbn_10: ['', ... ], isbn_13: ['', ... ]
    #                 libraryanything : ['', ... ], oclc: ['', ...], openlibrary: ['', ... ] }
    #                 NOT all keys will be there
    #   notes: ''
    #   number_of_pages: #
    #   publish_date: 'April 1, 1988' or '2012'
    #   publishers: [ { name } ]
    #   subjects: [ { name AKA tag category, url }, .. ]
    #   subtitle: '...'
    #   title: '...'
    #   url: 'https://...'

    # Use OL data, but augment with comments, series, summary
    # nvl(OL, CSV) for authors, # pages, publish date, publisher, title
    # Add flag for -u --update for Update matching ISBN
    # Add flag for -s --spreadsheet for Spreadsheet over OL key set TBD

    # A. Fetch existing data by ISBN, if any
    # B. if existing - do nothing unless --update provided
    # C. Build up Multiple dictionaries to meet data model following -s flag
    # D. Do Insert/Updates
    # E. commit only if -C present

def main():
    """Read ISBN values from a CSV, get data from API and store in database."""
    parser = build_arg_parser()
    args = validate_args(parser=parser)

    print("bulk_import execution start: {:%b-%d-%Y :%H:%M:%S}".format(datetime.datetime.now()))
    print("Parsing CSV file: {}".format(args.fname))

    # XXX: Should we parse entire CSV first and multi-fetch ISBNs? Or keep it at one call per row?

    headers = []
    for count, row in enumerate(csv.reader(open(args.fname, 'r'))):
        if count == 0:
            # Normalize headers to be used as dictionary keys
            headers = [x.strip().lower() for x in row]

            # Enforce required ISBN column
            if 'isbn' not in headers:
                print("ERROR: Required column ISBN not found in CSV file. Aborting.")
                raise SystemExit(1)

            continue

        # Covert data row into a dictionary
        csv_book = dict(zip(headers, row))

        # Don't waste an API hit on a blank ISBN value
        if not csv_book['isbn']:
            if args.verbose > 0:
                print("\tSkipping row #: {} - ISBN value is missing".format(count+1))
            continue

        # XXX: cache API results to avoid hammering server -c/-cache?
        # Fetch book from Open Library API
        if args.verbose > 0:
            print("\tFetching data for row #: {} with ISBN: {}".format(count, csv_book['isbn']))

        try:
            ol_book = search_isbn(isbn_list=[csv_book['isbn']])
        except requests.exceptions.HTTPError as err:
            print("\tERROR: HTTP error searching OpenLibrary.org")
            print("\t{}".format(err))
            continue

        if args.verbose > 1:
            pprint.pprint(csv_book)
            pprint.pprint(ol_book)
            print("\n")

        process_book(csv_book=csv_book, ol_book=ol_book)

    print("Import script complete at: {:%b-%d-%Y :%H:%M:%S}".format(datetime.datetime.now()))

#################################################################
# MAIN
#################################################################
if __name__ == '__main__':
    main()
