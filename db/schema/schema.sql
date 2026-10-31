SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);

CREATE TABLE public.api_keys (
    id integer NOT NULL,
    user_id integer NOT NULL,
    key_hash character varying(64) NOT NULL,
    prefix character varying(16) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    revoked_at timestamp with time zone
);

CREATE SEQUENCE public.api_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.api_keys_id_seq OWNED BY public.api_keys.id;

CREATE TABLE public.groups_cache (
    id integer NOT NULL,
    groups jsonb NOT NULL,
    fetched_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.groups_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.groups_cache_id_seq OWNED BY public.groups_cache.id;

CREATE TABLE public.lk_access_log (
    id bigint NOT NULL,
    user_id integer,
    login character varying(100),
    action character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    error text,
    duration_ms integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.lk_access_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.lk_access_log_id_seq OWNED BY public.lk_access_log.id;

CREATE TABLE public.notifications (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    kind character varying(20) NOT NULL,
    external_id character varying(100) NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    published character varying(50) NOT NULL,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.notifications_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;

CREATE TABLE public.personal_cache (
    user_id integer NOT NULL,
    kind character varying(50) NOT NULL,
    scope character varying(50) NOT NULL,
    data jsonb NOT NULL,
    fetched_at timestamp with time zone NOT NULL
);

CREATE TABLE public.personal_history (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    kind character varying(50) NOT NULL,
    scope character varying(50) NOT NULL,
    data jsonb NOT NULL,
    data_hash character varying(64) NOT NULL,
    captured_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.personal_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.personal_history_id_seq OWNED BY public.personal_history.id;

CREATE TABLE public.schedule_cache (
    group_name character varying(50) NOT NULL,
    is_session boolean NOT NULL,
    data jsonb NOT NULL,
    fetched_at timestamp with time zone NOT NULL
);

CREATE TABLE public.service_state (
    key character varying(50) NOT NULL,
    value jsonb NOT NULL,
    updated_at timestamp with time zone NOT NULL
);

CREATE TABLE public.student_profiles (
    user_id integer NOT NULL,
    surname character varying(100),
    name character varying(100),
    patronymic character varying(100),
    group_name character varying(50),
    course smallint,
    faculty text,
    specialty text,
    specialty_code character varying(50),
    specialization text,
    education_form character varying(50),
    degree_level character varying(50),
    degree_length character varying(50),
    enter_year character varying(20),
    status character varying(100),
    email character varying(200),
    updated_at timestamp with time zone NOT NULL
);

CREATE TABLE public.teacher_lessons (
    id integer NOT NULL,
    teacher character varying(200) NOT NULL,
    group_name character varying(50) NOT NULL,
    is_session boolean NOT NULL,
    weekday smallint,
    lesson_date date,
    pair smallint NOT NULL,
    subject character varying(300) NOT NULL,
    lesson_type character varying(100) NOT NULL,
    rooms jsonb NOT NULL,
    location character varying(200) NOT NULL,
    link text,
    date_from date NOT NULL,
    date_to date NOT NULL
);

CREATE SEQUENCE public.teacher_lessons_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.teacher_lessons_id_seq OWNED BY public.teacher_lessons.id;

CREATE TABLE public.tracked_groups (
    id integer NOT NULL,
    user_login character varying(100) NOT NULL,
    group_name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public.tracked_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.tracked_groups_id_seq OWNED BY public.tracked_groups.id;

CREATE TABLE public.user_sessions (
    user_id integer NOT NULL,
    token_enc text NOT NULL,
    jwt_enc text NOT NULL,
    jwt_refresh_enc text NOT NULL,
    refreshed_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);

CREATE TABLE public.users (
    id integer NOT NULL,
    guid character varying(64) NOT NULL,
    login character varying(100) NOT NULL,
    full_name character varying(300) NOT NULL,
    group_name character varying(50),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;

ALTER TABLE ONLY public.api_keys ALTER COLUMN id SET DEFAULT nextval('public.api_keys_id_seq'::regclass);

ALTER TABLE ONLY public.groups_cache ALTER COLUMN id SET DEFAULT nextval('public.groups_cache_id_seq'::regclass);

ALTER TABLE ONLY public.lk_access_log ALTER COLUMN id SET DEFAULT nextval('public.lk_access_log_id_seq'::regclass);

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);

ALTER TABLE ONLY public.personal_history ALTER COLUMN id SET DEFAULT nextval('public.personal_history_id_seq'::regclass);

ALTER TABLE ONLY public.teacher_lessons ALTER COLUMN id SET DEFAULT nextval('public.teacher_lessons_id_seq'::regclass);

ALTER TABLE ONLY public.tracked_groups ALTER COLUMN id SET DEFAULT nextval('public.tracked_groups_id_seq'::regclass);

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_key_hash_key UNIQUE (key_hash);

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.groups_cache
    ADD CONSTRAINT groups_cache_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.lk_access_log
    ADD CONSTRAINT lk_access_log_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_kind_external_id_key UNIQUE (user_id, kind, external_id);

ALTER TABLE ONLY public.personal_cache
    ADD CONSTRAINT personal_cache_pkey PRIMARY KEY (user_id, kind, scope);

ALTER TABLE ONLY public.personal_history
    ADD CONSTRAINT personal_history_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.schedule_cache
    ADD CONSTRAINT schedule_cache_pkey PRIMARY KEY (group_name, is_session);

ALTER TABLE ONLY public.service_state
    ADD CONSTRAINT service_state_pkey PRIMARY KEY (key);

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_pkey PRIMARY KEY (user_id);

ALTER TABLE ONLY public.teacher_lessons
    ADD CONSTRAINT teacher_lessons_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tracked_groups
    ADD CONSTRAINT tracked_groups_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tracked_groups
    ADD CONSTRAINT tracked_groups_user_login_group_name_key UNIQUE (user_login, group_name);

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (user_id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_guid_key UNIQUE (guid);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_login_key UNIQUE (login);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

CREATE INDEX ix_api_keys_user_id ON public.api_keys USING btree (user_id);

CREATE INDEX ix_lk_access_log_user_created ON public.lk_access_log USING btree (user_id, created_at);

CREATE INDEX ix_notifications_user_id ON public.notifications USING btree (user_id);

CREATE INDEX ix_personal_history_lookup ON public.personal_history USING btree (user_id, kind, scope, captured_at);

CREATE INDEX ix_teacher_lessons_group_name ON public.teacher_lessons USING btree (group_name);

CREATE INDEX ix_teacher_lessons_teacher ON public.teacher_lessons USING btree (teacher);

CREATE INDEX ix_tracked_groups_user_login ON public.tracked_groups USING btree (user_login);

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.lk_access_log
    ADD CONSTRAINT lk_access_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.personal_cache
    ADD CONSTRAINT personal_cache_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.personal_history
    ADD CONSTRAINT personal_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.student_profiles
    ADD CONSTRAINT student_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
