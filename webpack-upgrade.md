Installed webpack (via brew)
Ensure node version >=12.13 (check!)

TODO:
 * Work out how to get latest invenio-db revisions from alembic
 * Check whether we can upgrade invenio packages further

Tips
----
* Use `pip install -e.[all] hepdata` if setup.py changes
* `hepdata webpack buildall` if webpack.py has changed
* If getting keyerror not in manifest.json, check that the webpack build did not give eslint errors higher up.
* {{ webpack[...] }} in templates is provided by Flask-WebpackExt

Database upgrade notes
-------------
Alembic: need to do upgrade to get invenio_db changes.

Automatic changes:

`hepdata alembic upgrade`

Current versions:

```
hepdata=> select * from alembic_version ;
 version_num  
--------------
 c25ef2c50ffa       # invenio_userprofiles
 07fb52561c5c       # invenio_records
 999c62899c20       # invenio_pidstore
 e12419831262       # invenio_accounts
 bff1f190b9bd       # invenio_oauthclient
 04480be1593e       # invenio_access
(6 rows)
```

Manual table creation:
(Based on alembic upgrades in:
  * `invenio_db` (https://github.com/inveniosoftware/invenio-db/blob/v1.0.4/invenio_db/alembic/dbdbc1b19cf2_create_transaction_table.py)
  * `invenio_accounts`
  * `invenio_records`

TODO: Is there a better way to sort out the issues with alembic?

```
CREATE TABLE transaction (
  issued_at TIMESTAMP,
  id BIGINT CONSTRAINT pk_transaction PRIMARY KEY,
  remote_addr VARCHAR(50)  ,
  user_id INT,
  FOREIGN KEY (user_id) REFERENCES public.accounts_user(id)
);

CREATE SEQUENCE transaction_id_seq
AS integer
 START WITH 1
 INCREMENT BY 1
 NO MINVALUE
 NO MAXVALUE
 CACHE 1;

CREATE INDEX ix_transaction_user_id ON transaction USING btree(user_id);

CREATE TABLE records_metadata_version (
    created timestamp without time zone,
    updated timestamp without time zone,
    id uuid NOT NULL,
    json json,
    version_id integer,
    transaction_id bigint NOT NULL,
    end_transaction_id bigint,
    operation_type smallint NOT NULL
);

ALTER TABLE ONLY public.records_metadata_version
    ADD CONSTRAINT pk_records_metadata_version PRIMARY KEY (id, transaction_id);


CREATE INDEX ix_records_metadata_version_end_transaction_id ON public.records_metadata_version USING btree (end_transaction_id);

CREATE INDEX ix_records_metadata_version_operation_type ON public.records_metadata_version USING btree (operation_type);

CREATE INDEX ix_records_metadata_version_transaction_id ON public.records_metadata_version USING btree (transaction_id);

```
