-- Run from the folder that contains suite_runs.parquet, runs.parquet,
-- and attempts.parquet. No connection to PostgreSQL is needed.
CREATE OR REPLACE VIEW exported_suites AS
SELECT * FROM read_parquet('suite_runs.parquet');

CREATE OR REPLACE VIEW exported_runs AS
SELECT * FROM read_parquet('runs.parquet');

CREATE OR REPLACE VIEW exported_attempts AS
SELECT * FROM read_parquet('attempts.parquet');

CREATE OR REPLACE VIEW language_metrics AS
SELECT
    language,
    COUNT(*) AS tasks_evaluated,
    SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS tasks_solved,
    ROUND(AVG(CASE WHEN first_attempt_passed THEN 1.0 ELSE 0.0 END), 4) AS pass_at_1,
    ROUND(AVG(CASE WHEN passed THEN 1.0 ELSE 0.0 END), 4) AS pass_at_3,
    SUM(total_tokens) AS total_tokens,
    ROUND(AVG(total_tokens), 4) AS mean_tokens_per_task,
    MEDIAN(total_tokens) AS median_tokens_per_task,
    ROUND(SUM(repair_tokens)::DOUBLE / NULLIF(SUM(total_tokens), 0), 4) AS repair_token_share
FROM exported_runs
GROUP BY language;

CREATE OR REPLACE VIEW category_metrics AS
SELECT
    category,
    language,
    COUNT(*) AS tasks_evaluated,
    SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS tasks_solved
FROM exported_runs
GROUP BY category, language;

-- Compare tokens only on matching task pairs that *both* languages solved.
-- This is a ratio of sums, not the mean of per-task ratios.
CREATE OR REPLACE VIEW paired_metrics AS
WITH both_solved AS (
    SELECT
        zak.task_id,
        zak.total_tokens AS zak_tokens,
        python.total_tokens AS python_tokens
    FROM exported_runs AS zak
    JOIN exported_runs AS python
      ON zak.pair_id = python.pair_id
     AND zak.task_id = python.task_id
    WHERE zak.language = 'zak'
      AND python.language = 'python'
      AND zak.passed
      AND python.passed
)
SELECT
    COUNT(*) AS jointly_solved_tasks,
    SUM(zak_tokens) AS zak_tokens_on_joint_tasks,
    SUM(python_tokens) AS python_tokens_on_joint_tasks,
    ROUND(SUM(zak_tokens)::DOUBLE / NULLIF(SUM(python_tokens), 0), 4)
        AS zak_python_token_ratio
FROM both_solved;

-- The DuckDB CLI will display all the following result sets.
SELECT * FROM language_metrics ORDER BY language;
SELECT * FROM category_metrics ORDER BY category, language;
SELECT * FROM paired_metrics;
SELECT language, COUNT(*) AS total_attempts
FROM exported_attempts AS a
JOIN exported_runs AS r ON r.run_id = a.run_id
GROUP BY language
ORDER BY language;
