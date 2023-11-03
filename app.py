#!/usr/bin/env python
from flask import Flask, request, redirect, session, render_template
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager, current_user, login_user, logout_user

from flask_wtf import CSRFProtect

import requests
import base64
import hashlib
import os
import uuid
import sys
import secrets
import yaml
from pathlib import Path
import shutil
import uuid
import sqlite3

# from data import ACTORS
from db import init_db
from user import User
from forms import *
from data import env_attributes

from git import Repo

from atlassian.bitbucket import HTTPError, Cloud

from jinja2 import Environment
env = Environment()

# TODO:
# - auth against real google account
# - set up real dns

app = Flask(__name__)
app.debug = True
login_manager = LoginManager()
foo = secrets.token_urlsafe(16)
app.secret_key = foo

# Bootstrap-Flask requires this line
bootstrap = Bootstrap5(app)
# Flask-WTF requires this line
csrf = CSRFProtect(app)
# Flask-Login requires this line
login_manager.init_app(app)

# Naive database setup
try:
    init_db()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_URL = 'https://accounts.google.com/o/oauth2/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'

if not os.environ.get('GATEHOUSE_BITBUCKET_USER'):
    sys.exit("Error: GATEHOUSE_BITBUCKET_USER environment variable is not set")

if not os.environ.get('GATEHOUSE_BITBUCKET_PASSWORD'):
    sys.exit("Error: GATEHOUSE_BITBUCKET_PASSWORD environment variable is not set")

if not os.environ.get('GATEHOUSE_GOOGLE_CLIENT_ID'):
    sys.exit("Error: GATEHOUSE_GOOGLE_CLIENT_ID environment variable is not set")

if not os.environ.get('GATEHOUSE_GOOGLE_CLIENT_SECRET'):
    sys.exit("Error: GATEHOUSE_GOOGLE_CLIENT_SECRET environment variable is not set")

bb_user = os.environ.get('GATEHOUSE_BITBUCKET_USER')
bb_pass = os.environ.get('GATEHOUSE_BITBUCKET_PASSWORD')
CLIENT_ID = os.environ.get('GATEHOUSE_GOOGLE_CLIENT_ID')
CLIENT_SECRET = os.environ.get('GATEHOUSE_GOOGLE_CLIENT_SECRET')
SCOPE = os.getenv('GATEHOUSE_GOOGLE_SCOPE','openid%20email%20profile')
REDIRECT_URI = os.getenv('GATEHOUSE_REDIRECT_URI','http://127.0.0.1:5000/oauth2callback')
work_dir = os.getenv('GATEHOUSE_WORKDIR','/tmp/gatehouse')
git_ssh_key = os.getenv('GATEHOUSE_SSH_KEY', f'{Path.home()}/.ssh/gatehouse')
email_domain = os.getenv('GATEHOUSE_EMAIL_DOMAIN', 'mycompany.com')

# instantiate bitbucket cloud object
cloud = Cloud(url="https://api.bitbucket.org", username=bb_user, password=bb_pass, cloud=True)

def generate_state():
    state = base64.urlsafe_b64encode(hashlib.sha256(os.urandom(1024)).digest()).decode('utf-8')
    session['state'] = state
    return state

def str_to_class(classname):
    '''Convert a string to a class.'''
    return getattr(sys.modules[__name__], classname)

def read_generators():
    '''Read all generator definitions from YAML files.'''
    generators = []
    try:
        for filename in os.listdir('generators'):
            if filename.endswith('.yaml'):
                with open(os.path.join('generators', filename), 'r') as stream:
                    try:
                        tmp_dict = yaml.safe_load(stream)
                        tmp_dict['url_link'] = filename.split('.')[0]
                        generators.append(tmp_dict)
                    except yaml.YAMLError as exc:
                        return [exc, generators]
    except FileNotFoundError as e:
        return [e, generators]
    generators = sorted(generators, key=lambda x: x['name'])
    return [None, generators]

def return_generator(generator_name):
    '''Read a generator definition from a YAML file.'''
    filename = f'{generator_name}.yaml'
    response = []
    with open(os.path.join('generators', filename), 'r') as stream:
        try:
            response = yaml.safe_load(stream)
            return [None, response]
        except yaml.YAMLError as exc:
            return [exc, response]

def form_data_to_vars(form):
    '''Collect all form data and generate env vars from it.'''
    form_vars = {}
    form_data = list(form.data.keys())
    form_data.remove('csrf_token')
    form_data.remove('submit')
    for i in form_data:
        val_string = f"form.{i}.data"
        val_data = eval(val_string)
        form_vars[i] = val_data
    return form_vars

def ensure_dir(file_path):
    '''Ensure a directory exists.'''
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
        app.logger.debug(f"ensure_dir Created directory: {directory}")
    else:
        app.logger.debug(f"ensure_dir Directory exists: {directory}")

def generate_dirs(base_path, local_dir):
    '''Create a directory structure if needed.'''
    app.logger.debug(f"local_dir started: {local_dir}")
    for d in base_path.split('/'):
        local_dir = f"{local_dir}/{d}"
        app.logger.debug(f"local_dir now: {local_dir}")
        # for some reason this behind a directory unless I add {d}?
        ensure_dir(f"{local_dir}/{d}")
    return local_dir

def template_render(template, file_name, vars):
    '''Render a generator template.'''
    tmpl = env.from_string(template)
    template_out = tmpl.render(vars=vars)
    try:
        with open(f"{file_name}", "w") as outfile:
            outfile.write(template_out)
            return None
    except IOError as e:
        msg = f"ERROR: {e} - unable to write to {file_name}"
        app.logger.error(msg)
        return msg

def git_add_obj(repo, add_obj):
    '''Add and commit a file or directory to git.'''
    try:
        app.logger.debug(f"Adding: {add_obj}")
        repo.index.add(add_obj)
        repo.index.commit(f"Gatehouse update to {add_obj}")
        return None
    except:
        msg = f"ERROR: unable to add or commit {add_obj}"
        app.logger.error(msg)
        return msg

def git_push_branch(origin, branch):
    '''Push a git branch.'''
    try:
        push_res = origin.push(branch)[0]
        app.logger.debug(push_res.summary)
        return None
    except:
        msg = f"ERROR: unable to push {branch}"
        app.logger.error(msg)
        return msg

def bb_create_pr(generator_info, branch_name):
    '''Create a bitbucket PR for commit.'''
    repo_url = generator_info['repo']['url']
    try:
        workspace_key = repo_url.split(':')[1].split('/')[0]
        repository = repo_url.split('/')[1].split('.git')[0]
        project_key = generator_info['repo']['project_key']
        w = cloud.workspaces.get(workspace_key)
        p = w.projects.get(project_key)
        r = p.repositories.get(repository)
        reviewers = []
        for rev in r.default_reviewers.each():
            reviewers.append(rev.uuid)
        # create PR
        response = r.pullrequests.create(
            title=branch_name,
            source_branch=branch_name,
            destination_branch='main',
            reviewers=reviewers,
            close_source_branch=True
        )
        return f"https://bitbucket.org/{workspace_key}/{repository}/pull-requests/{str(response.id)}"
    except HTTPError as e:
        msg = f"ERROR: unable to create PR = {e}"
        app.logger.error(msg)
        return msg

def copy_tmpl_dir(template_data, base_dir, target_dir, repo):
    '''Copy the CONTENTS of template_data['tmpl_source_dir'] to local_dir.'''
    if 'tmpl_source_dir' in template_data:
        source_dir = f"{base_dir}/{template_data['tmpl_source_dir']}"
        try:
            app.logger.debug(f"Copying {source_dir} to {target_dir}..")
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
            # since we don't know exact pathes just add the whole dir
            git_response = git_add_obj(repo, target_dir)
            if git_response:
                return git_response
        except shutil.Error as e:
            msg = f"ERROR: unable to copy {source_dir} to {target_dir} - {e}"
            app.logger.error(msg)
            return msg

def return_target_file(template_data, form_vars):
    '''Return the target_file for a template.'''
    # start with target_file unset
    target_file = None
    # Try to set target_file from form_vars['name'] and form_vars['environment']
    if 'name' in form_vars and 'environment' in form_vars:
        target_file = f"{form_vars['name']}-{form_vars['environment']}.yaml"
    # if target_file is defined for template, use that instead
    if 'target_file' in template_data:
        target_file = template_data['target_file']
    app.logger.debug(f"target_file: {target_file}")
    return target_file

def commit_generator(generator_info, form_vars):
    '''Write all templates as files, commit, and create a PR.'''
    commit_uuid = str(uuid.uuid4().hex)
    git_ssh_cmd = f'ssh -i {git_ssh_key}'
    # copy unique dir here for multiple template processing
    local_base = f"{work_dir}/{commit_uuid}"
    app.logger.debug(f"cloning repo, creating {local_base}")
    repo_url = generator_info['repo']['url']
    repo = Repo.clone_from(f"git@{repo_url}", local_base, env=dict(GIT_SSH_COMMAND=git_ssh_cmd))
    origin = repo.remote(name="origin")
    branch_name = f"gatehouse/{commit_uuid}"
    # create new head and get it tracked in the origin
    new_branch = repo.create_head(branch_name)
    repo.head.reference = new_branch
    # prevent a cascading append of form_vars['name'] if we're processing multiple templates
    name_origin = form_vars['name']
    for t in generator_info['templates']:
        for bp in t['base_path']:
            bp_origin = bp
            if 'base_path_append_env' in form_vars:
                bp = f"{bp}/{form_vars['environment']}"
                app.logger.debug(f"bp: {bp}")
            if 'base_path_append_name' in form_vars:
                bp = f"{bp}/{name_origin}"
                app.logger.debug(f"bp: {bp}")
            # inject env_attributes for {environment} into form_vars if present
            if 'environment' in form_vars:
                form_vars['env_vars'] = env_attributes[form_vars['environment']]
            app.logger.debug(f"form_vars: {form_vars}")
            local_dir = local_base
            local_dir = generate_dirs(bp, local_dir)
            app.logger.debug(f"local_dir end: {local_dir}")
            if 'cp_base_path_origin' in form_vars:
                cp_local_dir = f"{local_base}/{bp_origin}"
            else:
                cp_local_dir = local_dir
            cp_response = copy_tmpl_dir(t, local_base, cp_local_dir, repo)
            if cp_response:
                return cp_response
            target_file = return_target_file(t, form_vars)
            # if name_override is set as a hidden field in the form, auto-generate name = name+env
            if 'name_override' in form_vars:
                form_vars['name'] = f"{name_origin}-{form_vars['environment']}"
            app.logger.debug(f"form_vars name now: {form_vars['name']}")
            # pass an error if we're unable to determine target_file
            if not target_file:
                return "ERROR: unable to determine target_file"
            add_file = f"{local_dir}/{target_file}"
            app.logger.debug(f"add_file: {add_file}")
            # check if the file exists before we generate it
            if os.path.exists(add_file):
                msg = f"ERROR: {add_file} already exists!"
                app.logger.error(msg)
                return msg
            tmpl_response = template_render(t['template'], add_file, form_vars)
            if tmpl_response:
                return tmpl_response
            # add file(s) to git
            git_add_obj(repo, add_file)
        # push branch
        push_response = git_push_branch(origin, branch_name)
        if push_response:
            return push_response
    # everything should be committed at this point so clean up
    shutil.rmtree(local_base)
    return bb_create_pr(generator_info, branch_name)

@login_manager.user_loader
def load_user(user_id):
    '''Flask-Login helper to retrieve a user from our db.'''
    return User.get(user_id)

@app.route('/')
def home():
    if current_user.is_authenticated:
        message = ""
        gen_results = read_generators()
        if gen_results[0]:
            message = gen_results[0]
        return render_template('home.html', generators=gen_results[1], message=message)
    else:
        return redirect('/login')

@app.route('/login')
def login():
    state = generate_state()
    auth_url = f'{GOOGLE_AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={SCOPE}&state={state}'
    return redirect(auth_url)

@app.route('/oauth2callback')
def oauth2callback():
    if request.args.get('state') != session.get('state'):
        return 'Invalid state', 400
    authorization_code = request.args.get('code')
    token_payload = {
        'code': authorization_code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    token_response = requests.post(GOOGLE_TOKEN_URL, data=token_payload)
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    userinfo_response = requests.get(GOOGLE_USERINFO_URL, headers={'Authorization': f'Bearer {access_token}'})
    userinfo = userinfo_response.json()
    if userinfo.get("verified_email"):
        unique_id = userinfo["id"]
        users_email = userinfo["email"]
        picture = userinfo["picture"]
        users_name = userinfo["name"]
    else:
        return "User email not available or not verified by Google.", 400
    # TODO: remove trackhearing.com when ready to deploy with 'real' auth config
    email_suffix = users_email.split('@')[1]
    if email_suffix != email_domain:
        return f"User email {users_email} not valid for this site!.", 400
    # Create a user in your db with the information provided by Google
    user = User(
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    )
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)
    # Begin user session by logging the user in
    login_user(user)
    return redirect('/')

@app.route('/logout')
def logout():
    logout_user()
    return render_template('logout.html')

@app.route('/generator/<id>', methods=['GET', 'POST'])
def generator(id):
    if not current_user.is_authenticated:
        return redirect('/login')
    message = ""
    # load form data from Class {id}Form
    gen_response = return_generator(id)
    if gen_response[0]:
        message = gen_response[0]
    generator_info = gen_response[1]
    form_name = f"{id}Form"
    form = str_to_class(form_name)()
    if form.validate_on_submit():
        form_vars = form_data_to_vars(form)
        response = commit_generator(generator_info, form_vars)
        app.logger.debug(f"response: {response}")
        return render_template('pr.html', pr_url=response)
    return render_template('generator.html', name=generator_info['name'], form=form, message=message)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    ensure_dir(work_dir)
    app.run()