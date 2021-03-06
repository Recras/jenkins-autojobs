#!/usr/bin/env python
# encoding: utf-8

'''
Automatically create jenkins jobs for the branches in a svn repository.
Documentation: http://gvalkov.github.com/jenkins-autojobs/
'''

from os import linesep, path
from sys import exit, argv
from subprocess import Popen, PIPE

from lxml import etree
from jenkins_autojobs.main import main as _main, debug_refconfig
from jenkins_autojobs.job import Job


def svn_ls(url, username=None, password=None, dirsonly=True):
    cmd = ['svn', 'ls', '--trust-server-cert', '--non-interactive']

    # :todo: plaintext (will probably have to use the bindings)
    if username: cmd += ['--username', username]
    if password: cmd += ['--password', password]

    cmd.append(url)
    out = Popen(cmd, stdout=PIPE).communicate()[0]
    out = out.decode('utf8').split(linesep)

    if dirsonly:
        out = [i.rstrip('/') for i in out if i.endswith('/')]

    return out


def list_branches(config):
    c = config
    branches = []

    for url in c['branches']:
        res = svn_ls(url, c['scm-username'], c['scm-password'])
        rel = url.replace(c['repo'], '').lstrip('/')
        res = [path.join(rel, i) for i in res]
        branches.extend(res)
    return branches


def create_job(branch, template, config, branch_config):
    '''Create a jenkins job.
       :param branch: svn branch name (ex: branches/feature-one)
       :param template: the config of the template job to use
       :param config: global config (parsed yaml)
       :param branch_config: the effective config for this branch
    '''

    print('\nprocessing branch: %s' % branch)

    # job names with '/' in them are problematic
    sanitized_branch = branch.replace('/', branch_config['namesep'])
    groups = branch_config['re'].match(branch).groups()

    # placeholders available to the 'substitute' and 'namefmt' options
    fmtdict = {
        'branch': branch.split('/')[-1],
        'path': branch.replace('/', branch_config['namesep']),
        'path-orig': branch,
    }

    job_name = branch_config['namefmt'].format(*groups, **fmtdict)
    job = Job(job_name, template, _main.jenkins)

    fmtdict['job_name'] = job_name

    print('. job name: %s' % job.name)
    print('. job exists: %s' % job.exists)

    try:
        scm_el = job.xml.xpath('scm[@class="hudson.scm.SubversionSCM"]')[0]
    except IndexError:
        msg = 'Template job %s is not configured to use SVN as an SCM'
        raise RuntimeError(msg % template)  # :bug:

    # set branch
    el = scm_el.xpath('//remote')[0]
    el.text = path.join(config['repo'], branch)

    # set the branch that git plugin will locally checkout to
    el = scm_el.xpath('//local')[0]
    el.text = '.'

    # set the state of the newly created job
    job.set_state(branch_config['enable'])

    # since some plugins (such as sidebar links) can't interpolate the job
    # name, we do it for them
    job.substitute(list(branch_config['substitute'].items()), fmtdict)

    job.create(branch_config['overwrite'], config['dryrun'])

    if config['debug']:
        debug_refconfig(branch_config)

def main(argv=argv, config=None):
    _main(argv[1:], config=config, create_job=create_job, list_branches=list_branches)

if __name__ == '__main__':
    main()
