-- Runs once when the Postgres volume is first initialised.
-- Creates the isolated database used by the backend test-suite.
CREATE DATABASE fogroom_test OWNER fogroom;
