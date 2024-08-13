CREATE SEQUENCE relatedrecid_id_seq
    INCREMENT 1
    START 1
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;
    
CREATE TABLE relatedrecid
(
    id integer NOT NULL DEFAULT nextval('relatedrecid_id_seq'::regclass),
    this_recid integer,
    related_recid integer,
    CONSTRAINT pk_relatedrecid PRIMARY KEY (id)
);

CREATE TABLE relatedrecid_identifier
(
    submission_id integer,
    relatedrecid_id integer,
    CONSTRAINT fk_relatedrecid_identifier_relatedrecid_id_relatedrecid FOREIGN KEY (relatedrecid_id)
        REFERENCES public.relatedrecid (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT fk_relatedrecid_identifier_submission_id_hepsubmission FOREIGN KEY (submission_id)
        REFERENCES public.hepsubmission (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
);

CREATE SEQUENCE relatedtable_id_seq
    INCREMENT 1
    START 1
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;

CREATE TABLE relatedtable
(
    id integer NOT NULL DEFAULT nextval('relatedtable_id_seq'::regclass),
    table_doi character varying(128) COLLATE pg_catalog."default",
    related_doi character varying(128) COLLATE pg_catalog."default",
    CONSTRAINT pk_relatedtable PRIMARY KEY (id)
);

CREATE TABLE relatedtable_identifier
(
    submission_id integer,
    relatedtable_id integer,
    CONSTRAINT fk_relatedtable_identifier_relatedtable_id_relatedtable FOREIGN KEY (relatedtable_id)
        REFERENCES public.relatedtable (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT fk_relatedtable_identifier_submission_id_datasubmission FOREIGN KEY (submission_id)
        REFERENCES public.datasubmission (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
);
