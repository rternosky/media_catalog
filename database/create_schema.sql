-- Copyright 2018 Robert Ternosky
DROP TABLE series_books;
DROP TABLE book_tags;
DROP TABLE book_authors;
DROP TABLE book_publishers;
DROP TABLE books;
DROP TABLE editions;
DROP TABLE tags;
DROP TABLE series;
DROP TABLE ratings;
DROP TABLE publishers;
DROP TABLE authors;

CREATE TABLE authors (
  author_id        SERIAL        PRIMARY KEY NOT NULL,
  author           VARCHAR(256)  NOT NULL,
  url              VARCHAR(2048) NOT NULL,
  UNIQUE(url)
);

CREATE TABLE publishers (
  publisher_id     SERIAL        PRIMARY KEY NOT NULL,
  publisher        VARCHAR(256)  NOT NULL,
  url              VARCHAR(2048) NOT NULL,
  UNIQUE(publisher),
  UNIQUE(url)
);

CREATE TABLE ratings (
  rating_id        SERIAL        PRIMARY KEY NOT NULL,
  rating           VARCHAR(64)   NOT NULL,
  UNIQUE(rating)
);

CREATE TABLE series (
  series_id        SERIAL        PRIMARY KEY NOT NULL,
  series           VARCHAR(256)  NOT NULL
);

CREATE TABLE tags (
  tag_id           SERIAL        PRIMARY KEY NOT NULL,
  tag              VARCHAR(64)   NOT NULL,
  UNIQUE(tag)
);

CREATE TABLE editions (
  edition_id       SERIAL        PRIMARY KEY NOT NULL,
  edition          VARCHAR(64)   NOT NULL,
  UNIQUE(edition)
);

CREATE TABLE books (
  book_id          SERIAL        PRIMARY KEY NOT NULL,
  isbn10           CHAR(10),
  isbn13           CHAR(13),
  title            CHAR(1024)    NOT NULL,
  subtitle         CHAR(1024),
  url              CHAR(2048)    NOT NULL,
  number_of_pages  INTEGER,
  cover_small      CHAR(1024),
  cover_medium     CHAR(1024),
  cover_large      CHAR(1024),
  publish_date     DATE,
  edition_id       INTEGER,
  rating_id        INTEGER,
  date_added       DATE          NOT NULL,
  UNIQUE(url),
  FOREIGN KEY (edition_id) REFERENCES editions (edition_id),
  FOREIGN KEY (rating_id) REFERENCES ratings (rating_id)
);

CREATE TABLE book_publishers (
  book_id         INTEGER        NOT NULL,
  publisher_id    INTEGER        NOT NULL,
  UNIQUE(book_id, publisher_id),
  FOREIGN KEY (book_id) REFERENCES books (book_id),
  FOREIGN KEY (publisher_id) REFERENCES publishers (publisher_id)
);

CREATE TABLE book_authors (
  book_id         INTEGER        NOT NULL,
  author_id       INTEGER        NOT NULL,
  is_primary      BOOLEAN        NOT NULL,
  UNIQUE(book_id, author_id),
  FOREIGN KEY (book_id) REFERENCES books (book_id),
  FOREIGN KEY (author_id) REFERENCES authors (author_id)
);

CREATE TABLE book_tags (
  book_id        INTEGER         NOT NULL,
  tag_id         INTEGER         NOT NULL,
  UNIQUE(book_id, tag_id),
  FOREIGN KEY (book_id) REFERENCES books (book_id),
  FOREIGN KEY (tag_id) REFERENCES tags (tag_id)
);

CREATE TABLE series_books (
  series_id      INTEGER         NOT NULL,
  book_id        INTEGER         NOT NULL,
  seq            INTEGER         NOT NULL,
  UNIQUE(series_id, book_id),
  UNIQUE(series_id, seq),
  FOREIGN KEY (series_id) REFERENCES series (series_id),
  FOREIGN KEY (book_id) REFERENCES books (book_id),
  CHECK (seq > 0)
);
