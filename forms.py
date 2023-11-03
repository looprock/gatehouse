from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, Length, Regexp, URL

from data import env_attributes

global team_choices
team_choices = [('backend', 'Backend'), ('frontend', 'Frontend'), ('platform-eng', 'Platform Engineering')]

global env_choices
env_choices = []
for env in env_attributes:
    env_choices.append((env, env_attributes[env]['friendly_name']))

class test1Form(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(2, 128), Regexp('^[a-zA-Z0-9-]+$')])
    team = SelectField(u'Team', choices=team_choices)
    managed_by = SelectField(u'Managed By', choices=team_choices)
    billing = SelectField(u'Billing', choices=team_choices)
    runbook = StringField('Runbook', validators=[DataRequired(), URL()])
    environment = SelectField(u'Environment', choices=env_choices)
    submit = SubmitField('Submit')

class argocd_appForm(FlaskForm):
    name = StringField('Name [Valid characters:  a-Z,0-9,-]', validators=[DataRequired(), Length(2, 128), Regexp('^[a-zA-Z0-9-]+$')])
    git_path = StringField('Git Path [relative path, RE: kubernetes/helm/test-service]', validators=[DataRequired(), Length(2, 512), Regexp('^(?!/)([^/\0]+(/)?)+$')])
    team = SelectField(u'Team', choices=team_choices)
    managed_by = SelectField(u'Managed By', choices=team_choices)
    environment = SelectField(u'Environment', choices=env_choices)
    # setting name_override will cause the name to be overridden as {name}-{environment}
    name_override = HiddenField('Filename Override')
    # setting base_path_append_env will cause '/{environment}' to be appended to all base_path entries
    base_path_append_env = HiddenField('Base Path Append Env')
    submit = SubmitField('Submit')

class s3Form(FlaskForm):
    name = StringField('Name [Valid characters:  a-Z,0-9,-]', validators=[DataRequired(), Length(2, 128), Regexp('^[a-zA-Z0-9-]+$')])
    team = SelectField(u'Team', choices=team_choices)
    managed_by = SelectField(u'Managed By', choices=team_choices)
    billing = SelectField(u'Billing', choices=team_choices)
    environment = SelectField(u'Environment', choices=env_choices)
    # setting name_override will cause the name to be overridden as {name}-{environment}
    name_override = HiddenField('Filename Override')
    # setting base_path_append_name will cause '/{name}' to be appended to all base_path entries
    base_path_append_name = HiddenField('Base Path Append Name')
    submit = SubmitField('Submit')

class helm_extpostgresoperatorForm(FlaskForm):
    name = StringField('Database Name [Valid characters:  a-Z,0-9,-]', validators=[DataRequired(), Length(2, 128), Regexp('^[a-zA-Z0-9-]+$')])
    # TODO: this should be a dropdown pulled from AWS API or something similar
    instance = StringField('Database Instance [Valid characters:  a-Z,0-9,-]', validators=[DataRequired(), Length(2, 128), Regexp('^[a-zA-Z0-9-]+$')])
    environment = SelectField(u'Environment', choices=env_choices)
    # setting base_path_append_env will cause '/{environment}' to be appended to all base_path entries
    base_path_append_env = HiddenField('Base Path Append Env')
    # copy tmpl_source_dir to base_path (not base_path/{environment})
    cp_base_path_origin = HiddenField('Copy Base Path Origin')
    submit = SubmitField('Submit')