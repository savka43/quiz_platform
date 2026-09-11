"""Question options, question favorites and immutable attempt snapshots.

Revision ID: ab92110c7d02
Revises: 044028594a61
"""
from alembic import op
import sqlalchemy as sa

revision = 'ab92110c7d02'
down_revision = '044028594a61'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tests', sa.Column('description', sa.Text(), nullable=False, server_default=''))
    op.add_column('tests', sa.Column('source', sa.String(20), nullable=False, server_default='manual'))
    op.add_column('tests', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.alter_column('questions', 'correct_answer', server_default='')
    op.add_column('questions', sa.Column('question_type', sa.String(20), nullable=False, server_default='text'))
    op.add_column('questions', sa.Column('position', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('questions', sa.Column('explanation', sa.Text(), nullable=False, server_default=''))
    op.add_column('questions', sa.Column('blanks', sa.JSON(), nullable=False, server_default='[]'))
    op.create_table('answer_options',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.UniqueConstraint('question_id', 'position'))
    op.create_index('ix_answer_options_question_id', 'answer_options', ['question_id'])
    op.create_table('favorites',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'question_id'))
    op.create_index('ix_favorites_user_id', 'favorites', ['user_id'])
    op.create_index('ix_favorites_question_id', 'favorites', ['question_id'])
    op.drop_constraint('attempts_test_id_fkey', 'attempts', type_='foreignkey')
    op.alter_column('attempts', 'test_id', nullable=True)
    op.create_foreign_key('attempts_test_id_fkey', 'attempts', 'tests', ['test_id'], ['id'], ondelete='SET NULL')
    op.add_column('attempts', sa.Column('test_title', sa.String(200), nullable=False, server_default=''))
    op.add_column('attempts', sa.Column('score', sa.Float(), nullable=True))
    op.create_table('attempt_questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('attempt_id', sa.Integer(), sa.ForeignKey('attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_question_id', sa.Integer(), sa.ForeignKey('questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.UniqueConstraint('attempt_id', 'position'))
    op.create_index('ix_attempt_questions_attempt_id', 'attempt_questions', ['attempt_id'])
    op.create_index('ix_attempt_questions_source_question_id', 'attempt_questions', ['source_question_id'])
    op.drop_constraint('attempt_answers_question_id_fkey', 'attempt_answers', type_='foreignkey')
    op.alter_column('attempt_answers', 'question_id', nullable=True)
    op.create_foreign_key('attempt_answers_question_id_fkey', 'attempt_answers', 'questions', ['question_id'], ['id'], ondelete='SET NULL')
    op.add_column('attempt_answers', sa.Column('attempt_question_id', sa.Integer(), nullable=True))
    op.create_foreign_key('attempt_answers_snapshot_fkey', 'attempt_answers', 'attempt_questions', ['attempt_question_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('attempt_answers_snapshot_key', 'attempt_answers', ['attempt_question_id'])
    op.add_column('attempt_answers', sa.Column('selected_option_ids', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('attempt_answers', sa.Column('blank_answers', sa.JSON(), nullable=False, server_default='[]'))
    # Preserve legacy text questions and existing history without dropping user data.
    op.execute('''UPDATE questions SET position = ranked.pos FROM
        (SELECT id, row_number() OVER (PARTITION BY test_id ORDER BY id) - 1 AS pos FROM questions) ranked
        WHERE questions.id = ranked.id''')
    op.execute('UPDATE attempts SET test_title = tests.title FROM tests WHERE attempts.test_id = tests.id')
    op.execute('''INSERT INTO attempt_questions (attempt_id, source_question_id, position, payload)
        SELECT a.id, q.id, q.position, json_build_object(
            'id', q.id, 'text', q.text, 'question_type', 'text', 'correct_answer', q.correct_answer,
            'blanks', '[]'::json, 'options', '[]'::json, 'explanation', '')
        FROM attempts a JOIN questions q ON q.test_id = a.test_id''')
    op.execute('''UPDATE attempt_answers aa SET attempt_question_id = aq.id
        FROM attempt_questions aq WHERE aq.attempt_id = aa.attempt_id AND aq.source_question_id = aa.question_id''')
    op.execute('''UPDATE attempts a SET score = (
        SELECT round(100.0 * count(*) FILTER (WHERE aa.is_correct) / nullif(count(*), 0), 2)
        FROM attempt_questions aq LEFT JOIN attempt_answers aa ON aa.attempt_question_id = aq.id
        WHERE aq.attempt_id = a.id) WHERE a.finished_at IS NOT NULL''')


def downgrade():
    # A downgrade would lose snapshots/options and cannot restore deleted source questions.
    # Refuse rather than silently delete history or practice attempts with NULL test_id.
    raise RuntimeError('This data-preserving migration cannot be downgraded automatically; restore a backup instead')
