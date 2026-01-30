CREATE TABLE tt_posts_difficulty (
	ver int4 NOT NULL,
	creationdate timestamp NOT NULL,
	id int4 NOT NULL,
	difficulty_level int4 NULL,
	CONSTRAINT tt_posts_difficulty_pkey PRIMARY KEY (ver, creationdate, id)
);

CREATE TABLE tt_posts_difficulty_annotated (
	id int4 NOT NULL,
	CONSTRAINT tt_posts_difficulty_annotated_pkey PRIMARY KEY (id)
);

CREATE TABLE tt_posts_difficulty_done (
	ver int4 NOT NULL,
	creationdate timestamp NOT NULL,
	id int4 NOT NULL,
	CONSTRAINT tt_posts_difficulty_done_pkey PRIMARY KEY (ver, creationdate, id)
);
CREATE INDEX idx_tt_posts_difficulty_done_01 ON tt_posts_difficulty_done USING btree (ver, creationdate);


CREATE TABLE tt_posts_difficulty_target (
	ver int4 NOT NULL,
	creationdate timestamp NOT NULL,
	id int4 NOT NULL,
	CONSTRAINT tt_posts_difficulty_target_pkey PRIMARY KEY (ver, creationdate, id)
);
CREATE INDEX idx_tt_posts_difficulty_target_01 ON tt_posts_difficulty_target USING btree (ver, creationdate);


-- table for date 
CREATE TABLE ma_year (
	"year" varchar(5) NULL
);

CREATE TABLE date_master (
	"date" timestamptz NULL
);
