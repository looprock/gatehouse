# About
Gatehouse is a GitOps driven dashboard to allow developers to provision resources with best practices and guardrails in place. The intention is for gatehouse to provide a simple form interface to generate configuration from templates that will be checked into git and then acted on by tools such as Atlantis or argoCD, who will handle the heavy lifting.

# Creating a new generator

1. create a generator definition file with metadata under generators/
2. add a form section to forms.py of the name <generators/filename minus '.yaml'>Form in forms.py (RE: if you create 'generators/foo.yaml', you would create a form class defining the data you want to capture called 'fooForm' in forms.py)

## generator configuration

*Note:* All fields are required unless specified otherwise in notes below.

```
name: The name that shows up in the first page of generators, RE: Create S3 Bucket
description: The description that shows up in the first page of generators, RE: Make an S3 Bucket
repo:
  url: The bitbucket URL for the repo (minus login and protocol), RE: bitbucket.org:homestoryre/platform_eng_tools.git
  project_key: The bitbucket project key, RE: OP
templates: - This section is a list of templates we want generated
  - base_path: A list of directories you want the above file written to (see Special form values below), RE: 
    ' - terraform/us-east-2/s3'
    ' - terraform/us-west-1/s3'
    target_file: OPTIONAL - The filename to write the template to, RE: test1.yaml. If not defined, this will default to: "{name}-{environment}"
    tmpl_source_dir: OPTIONAL - if this is defined, the *contents* of this directory (not the directory itself) will be written to the base_path directories. This can be useful if we have file sets that *aren't* templates (like helm charts minus the values files) we want to duplicate to base_path, RE: templates/s3
    template: | - Everything after this line is the jinja2 template use to create target_file, RE:
      apiVersion: v1
      kind: Bar
      metadata:
        name: {{ vars['name'] }}
        labels:
          app: {{ vars['name'] }}
        annotations:
          tag.homestoryrewards.com/team: {{ vars['team'] }}
          tag.homestoryrewards.com/managed_by: {{ vars['managed_by'] }}
          tag.homestoryrewards.com/billing: {{ vars['billing'] }}
          tag.homestoryrewards.com/runbook: {{ vars['runbook'] }}
          tag.homestoryrewards.com/environment: {{ vars['environment'] }}
      spec:
        selector:
          app: {{ vars['name'] }}
        type: Bar
```

## Special form values

*base_path_append_env = HiddenField('Base Path Append Env')* - this will trigger '/{environment}' to be appended to all base_path entries. Useful for things like argoCD project directory generation: argocd/project/{env}

*base_path_append_name = HiddenField('Base Path Append Name')* - this will trigger '/{name}' to be appended to all base_path entries. Useful for things like terraform directory generation: some/path/s3/{name}.

*cp_base_path_origin = HiddenField('Copy Base Path Origin')* - use the original base_path when copying the contents from tmpl_source_dir. This is helpful with Helm where you the shared configuration to be under a root dir with a values file under root/{environment}

*name_override = HiddenField('Filename Override')* - this will cause the name to be overridden with form values "{name}-{environment}" (same as the default value for target_file.) This is intended to enforce naming conventions without requiring people filling out the form to be aware of them.

# Limitations

Currently gatehouse only supports a single git repository per generator.

Gatehouse also currently only supports bitbucket.

# Notes

I ended up needing to downgrade and pin:
* werkzeug = "^2.3.7"
* flask = "^2.3.3"
* flask-wtf = "1.1.1"

to support flask-login for session management

[... and apparently I'm not alone](https://blog.miguelgrinberg.com/post/we-have-to-talk-about-flask)

# References

[google auth](https://devguide.dev/blog/flask-google-sign-in)

[google auth 2](https://realpython.com/flask-google-login/)

[flask-WTF](https://python-adv-web-apps.readthedocs.io/en/latest/flask_forms.html)

[Styling 1](https://blog.miguelgrinberg.com/post/beautiful-interactive-tables-for-your-flask-templates)

[Styling 2](https://arshovon.com/snippets/flask-bootstrap-navbar/)

[git](https://gitpython.readthedocs.io/en/stable/quickstart.html)

[bitbucket 1](https://stackoverflow.com/questions/70653665/how-to-authenticate-to-bitbucket-with-atlassian-python-api)

[bitbucket 2](https://atlassian-python-api.readthedocs.io/bitbucket.html)

[bitbucket 3](https://github.com/atlassian-api/atlassian-python-api/blob/master/examples/bitbucket/bitbucket_cloud_oo.py)

[bitbucket 4](https://github.com/atlassian-api/atlassian-python-api/blob/master/atlassian/bitbucket/cloud/repositories/pullRequests.py)