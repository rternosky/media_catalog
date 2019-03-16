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
import pickle
import pprint

import requests
import sqlalchemy
import sqlalchemy.orm as sqlorm

import media_schema

DEFAULT_BASE_URL = 'https://openlibrary.org/api/books'

##############################################################
# Argument Handling
##############################################################
def build_arg_parser():
    """Build an argpare.ArgumentParser() object

    :returns: argparse.ArgumentParser()
    """
    parser = argparse.ArgumentParser(description='Import books into database from CSV')

    # Positional Arguments
    parser.add_argument('fname', action='store', help='CSV filename to use as input')

    # Named arguments, i.e. starting with "-" or "--"
    # Cache options
    parser.add_argument('-c', '--cachedir', dest='cachedir', required=False,
                        default='./cache', help='Cache directory')
    parser.add_argument('-d', '--disablecache', dest='disable_cache', action='store_true',
                        required=False, default=False,
                        help='Do not use cache files where possible (default: no)')

    # Database options
    parser.add_argument('-n', '--dbname', dest='db_name', required=False,
                        default='media', help='Database Name (default: media)')
    parser.add_argument('-p', '--dbpasswd', dest='db_password', required=True,
                        help='Database Password')
    parser.add_argument('-u', '--dbuser', dest='db_user', required=False,
                        default='media', help='Database Username (default: media)')
    parser.add_argument('-C', '--commit', dest='commit', action='store_true', required=False,
                        default=False, help='Commit database work? (default: no)')
    parser.add_argument('-H', '--dbhost', dest='db_host', required=False,
                        default='localhost', help='Database Host (default: localhost)')
    parser.add_argument('-P', '--dbport', dest='db_port', required=False, type=int,
                        default=5432, help='Database Port (default: 5432)')

    # Other
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
        parser.error('filename : {0} does not exist or cannot be reached'.format(args.fname))

    if args.cachedir:
        if not os.path.exists(args.cachedir):
            try:
                os.makedirs(args.cachedir)
            except OSError as err:
                parser.error('While ensuring existence of directory: {0}, Error:\n{1}'.format(
                    args.cachedir, err))

    return args

##############################################################
# Data Fetching
##############################################################
def search_isbn(isbn):
    """Search OpenLibrary.org for books using a list of ISBN numbers.

    :param isbn: String. ISBN string value.
    :returns: Dictionary. {info from openlibrary}
    :raises requests.exceptions.HTTPError on failure
    :precondition: isbn is string in ISBN format
    """
    query_string = 'jscmd=data&format=json&bibkeys={0}'.format(isbn)
    full_url = "{0}?{1}".format(DEFAULT_BASE_URL, query_string)
    resp = requests.get(full_url)
    resp.raise_for_status()

    # OL returns {'ISBN:#######': {book info} }
    # Return just {book info}
    return list(resp.json().values())[0]

def fetch_book_details(isbn, cache_dir, disable_cache, verbose):
    """Fetch book details by ISBN

    Use OpenLibrary if we haven't seen it or cache is disabled.
    Write OL data to a cache file unless cache is disabled

    :param isbn: String. ISBN number
    :param cache_dir: String. Full path to cache directory.
    :param disable_cache: Boolean. Should we not use caching at all?
    :param verbose: Integer. Verbosity level
    :returns: Tuple. (Dictionary, String).
           ({} = ERROR OR {Data from OpenLibrary. Either real time or from cache},
            '' = Error message or empty string on success)
    """
    cache_file = '{0}/isbn{1}.dat'.format(cache_dir, isbn)

    # Try to get cache file first unless directed otherwise [-d]
    if not disable_cache:
        if os.path.exists(cache_file):
            if verbose > 0:
                print("\tLoading ISBN: {0} from cache file: {1}".format(isbn, cache_file))

            with open(cache_file, 'rb') as fhandle:
                ol_book = pickle.load(fhandle)

            return (ol_book, '')

    # Either no cache file found or [-d] present. Use OpenLibrary to fetch data
    # Fetch book from Open Library API
    try:
        ol_book = search_isbn(isbn=isbn)
    except requests.exceptions.HTTPError as err:
        error = "ERROR: HTTP error searching OpenLibrary.org: {0}".format(err)
        return ({}, error)

    # Since we got from an API write cache file always
    if verbose > 1:
        print("\tWriting cache file: {0}".format(cache_file))

    with open(cache_file, 'wb') as fhandle:
        pickle.dump(ol_book, fhandle, pickle.HIGHEST_PROTOCOL)

    return (ol_book, '')

##############################################################
# Processing
##############################################################
def schema_to_dict(schema_object):
    """Convert a SQLAlchemy schema object to a dictionary.
    :param schema_object: SQLALchemy Table() object
    :returns: Dictionary
    """
    cols = schema_object.__table__.columns.keys()
    return dict((x, getattr(schema_object, x)) for x in cols)

def populate_publisher(session, csv_book, ol_book, existing):
    """Add the publisher(s) to the database if not already there.

    :param session: SQLAlchemy.org.Session() object
    :param csv_book: Dictionary. Row from CSV file representing a book
    :param ol_book: Dictionary. Data from Open Library for ISBN from csv_book
    :param existing: Dictionary. Publishers we've seen. MODIFIED in here
    """
    # XXX: Consider cases where:
    # A) publishers not in OL
    # B) publishers not in CSV
    # C) publishers not in OL or CSV

    # CSV['publisher'] = 'Ace Books'
    # OL['publishers'] = [{'name': 'Ace'}]
    for publisher in ol_book['publishers']:
        if publisher['url'] in existing:
            print("Skipping Publisher {name} ({url})".format(**publisher))
            # XXX: compare before returning?
            return existing[publisher['url']]

        # Not pre-existing. Insert and update existing
        print("Creating publisher: {name} ({url})".format(**publisher))
        new_publisher = media_schema.Publisher()
        new_publisher.publisher = publisher['name']
        new_publisher.url = publisher['url']
        session.add(new_publisher)

        # Fetch the SERIAL generated publisher_id value
        session.flush()

        # Add to existing in-case multiple adds from a single import
        existing[new_publisher.url] =  schema_to_dict(schema_object=new_publisher)


def populate_author(session, csv_book, ol_book, existing):
    """Add the author(s) to the database if not already there.

    :param session: SQLAlchemy.org.Session() object
    :param csv_book: Dictionary. Row from CSV file representing a book
    :param ol_book: Dictionary. Data from Open Library for ISBN from csv_book
    :param existing: Dictionary. Authors we've seen. MODIFIED in here
    """
    # XXX: Consider cases where:
    # A) authors not in OL
    # B) authors not in CSV
    # C) authors not in OL or CSV

    # CSV['authors'] = 'Justin Cronin'
    # OL['authors'] = [{'name': 'Justin Cronin', 'url': 'https://...'}, ... ]
    for author in ol_book['authors']:
        if author['url'] in existing:
            print("Skipping Author {name} ({url})".format(**author))
            # XXX: compare before returning?
            return existing[author['url']]

        # Not pre-existing. Insert and update existing
        print("Creating author: {name} ({url})".format(**author))
        new_author = media_schema.Author()
        new_author.author = author['name']
        new_author.url = author['url']
        session.add(new_author)

        # Fetch the SERIAL generated author_id value
        session.flush()

        # Add to existing in-case multiple adds from a single import
        existing[new_author.url] =  schema_to_dict(schema_object=new_author)

def process_book(session, csv_book, ol_book, existing_data):
    """Process a book and write to database.

    :param session: SQLAlchemy.org.Session() object
    :param csv_book: Dictionary. Row from CSV file representing a book
    :param ol_book: Dictionary. Data from Open Library for ISBN from csv_book
    :param existing_data: Dictionary. Data from database. MODIFIED in here
    """
    # Commbine the CSV and OL book data and store in the database without creating duplication
    # Since there is duplicated data between the 2 sources  the rule is:
    #   Use OL data, but augment with comments, series, summary from CSV
    #   nvl(OL, CSV) for authors, # pages, publish date, publisher, title

    # XXX: turn into dispatch table - if the signature is always the same
    author = populate_author(session=session, csv_book=csv_book, ol_book=ol_book,
                             existing=existing_data['authors'])

    # 2. Create Publisher
    #publisher = populate_publisher(session=session, csv_book=csv_book, ol_book=ol_book,
    #                               existing=existing_data['publishers'])

    # 3. Create Edition
    # 4. Create Series
    # 5. Create Book
    # 6. Create Book_Authors
    # 7. Create Book_Publisherw
    # 8. Create Series_Books
    # 9. Tags, Ratings, Book_Tags

def index_db_data(session):
    """Read data from database into index to optimize large bulk loads.

    :param session: SQLAlchemy.org.Session() object
    :returns: Dictionary. { tablename: { INDEX KEY: {table row } } }
    """
    # Index all data as a cache to avoid hammering the database later
    # Eery object will be a dict of format: { KEY: {} }. The KEY column
    # may vary by datatype. Our in memory cache will be for format:
    # { TYPE: { KEY: {} } }
    existing_data = {}

    # table: authors. indexed by URL { url: {} }
    existing_data['authors'] = {}
    for author in session.query(media_schema.Author):
        existing_data['authors'][author.url] = schema_to_dict(schema_object=author)

    # table: publishers: indexed by URL { url: {} }
    existing_data['publishers'] = {}
    for author in session.query(media_schema.Publisher):
        existing_data['publishers'][publisher.url] = schema_to_dict(schema_object=publisher)

    return existing_data

def main():
    """Read ISBN values from a CSV, get data from API and store in database."""
    parser = build_arg_parser()
    args = validate_args(parser=parser)

    print("bulk_import execution start: {0:%b-%d-%Y :%H:%M:%S}".format(datetime.datetime.now()))
    print("Parsing CSV file: {0}".format(args.fname))

    url = 'postgresql://{0}:{1}@{2}:{3}/{4}'.format(args.db_user, args.db_password, args.db_host,
                                                    args.db_port, args.db_name)
    engine = sqlalchemy.create_engine(url, client_encoding='utf8', echo=False)
    session_handle = sqlorm.sessionmaker(bind=engine)
    session = session_handle()

    # Setup cache of data from database
    existing_data = index_db_data(session=session)

    headers = []
    success_count = 0
    total_count = 0
    for count, row in enumerate(csv.reader(open(args.fname, 'r'))):
        if count == 0:
            # Normalize headers to be used as dictionary keys
            headers = [x.strip().lower() for x in row]

            # Enforce required ISBN column
            if 'isbn' not in headers:
                print("ERROR: Required column ISBN not found in CSV file. Aborting.")
                raise SystemExit(1)

            continue

        total_count += 1

        # Covert data row into a dictionary
        csv_book = dict(zip(headers, row))

        # Don't waste time and a potential API hit on a blank ISBN value.
        if not csv_book['isbn']:
            if args.verbose > 0:
                print("\tSkipping row #: {0} - ISBN value is missing".format(count+1))
            continue

        if args.verbose > 0:
            print("\tFetching data for row #: {0} with ISBN: {1}".format(count, csv_book['isbn']))

        # We cache API results. Get from there unless directed otherwise
        ol_book, error = fetch_book_details(isbn=csv_book['isbn'], cache_dir=args.cachedir,
                                            disable_cache=args.disable_cache, verbose=args.verbose)
        if not ol_book:
            # Error in fetch_book_details
            print("\t" + error)
            continue

        if args.verbose > 1:
            print("\n")
            print("CSV Data:")
            pprint.pprint(csv_book)
            print("OL Data:")
            pprint.pprint(ol_book)
            print("\n")

        process_book(session=session, csv_book=csv_book, ol_book=ol_book,
                     existing_data=existing_data)
        success_count += 1

    if args.commit:
        print("[-C] is present, committing transaction(s)")
        session.commit()
    else:
        print("[-C] missing, rolling back transaction(s)")
        session.rollback()

    session.close()

    print("Import script complete at: {0:%b-%d-%Y :%H:%M:%S}".format(datetime.datetime.now()))
    print("Successfully processed: {0} / {1} books in CSV file".format(success_count, total_count))

#################################################################
# MAIN
#################################################################
if __name__ == '__main__':
    main()
