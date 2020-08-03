#!/usr/bin/env python3
"""
Wrapper tool for managing jenkins jobs via jenkins job builder
"""
from jenkins_job_manager.core import JenkinsJobManager

import click
import logging
import os

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jjm")

HERE = os.path.dirname(os.path.realpath(__file__))


@click.group()
@click.option("--debug", "-d", is_flag=True)
@click.option("--working-dir", "-C", default=None, help="change to this directory ")
@click.option("--url", help="jenkins base url")
@click.pass_context
def jjm(ctx, debug, working_dir, url):
    """Jenkins Job Management"""
    if debug:
        log.setLevel(logging.DEBUG)
    if working_dir:
        os.chdir(working_dir)

    config = {}
    if url:
        config["url"] = url
    jjm = JenkinsJobManager(config_overrides=config)
    ctx.obj = jjm
    if not jjm.config.url:
        click.echo(
            "\n"
            "ERROR: No jenkins url configured.\n"
            "Create a ./jjm.ini file with contents:\n"
            "    [jenkins]\n"
            "    url = https://yourjenkinsurl.com/\n"
        )
        raise click.exceptions.Exit(1)


@jjm.command(name="login")
@click.pass_obj
def jjm_login(obj: JenkinsJobManager):
    """store login config per url"""
    jjm = obj
    jconf = jjm.config
    jurl = jconf.url
    username, password = jconf.username, jconf.password
    if username and password:
        click.secho(f"Auth already configured for this jenkins!", fg="red")
        click.secho(f"{jconf}", fg="white")
        click.confirm("overwrite?", abort=True)

    click.secho("Configuring login info for:", fg="green")
    click.secho(f"\t{jurl}", fg="white")

    click.secho(f"\nEnter username, go to {jurl}/whoAmI/ if unsure.")
    username = click.prompt("username", type=str)

    click.secho(
        f"\nEnter api key. go to {jurl}/user/{username}/configure to make a new one."
    )
    password = click.prompt("api key", type=str, hide_input=True)
    log.debug("entered username=%r password=%r", username, password)

    jconf.username, jconf.password = username, password
    if jjm.check_authentication():
        click.secho(f"Success! Saving to {jconf.user_conf_path}", fg="green")
        jconf.update_user_conf_auth(username, password)
    else:
        click.secho(f"Bad Authentication, try again.", fg="red")
        raise click.exceptions.Exit(2)


@jjm.command(name="check")
@click.pass_obj
def jjm_check(obj: JenkinsJobManager):
    """check syntax/config"""
    obj.generate_jjb_xml()


def check_auth(obj: JenkinsJobManager):
    """cli helper for auth check"""
    if not obj.check_authentication():
        click.secho(f"Bad login detected for {obj.config}", fg="red")
        click.echo("Try the login subcommand")
        raise click.exceptions.Exit(1)


def handle_plan_report(obj: JenkinsJobManager, use_pager=True) -> bool:
    """cli helper for plan report"""

    def output_format(line):
        if line.startswith("+"):
            return click.style(line, fg="green")
        elif line.startswith("-"):
            return click.style(line, fg="red")
        else:
            return line

    if obj.detected_changes():
        gen_lines = map(output_format, obj.plan_report())
        if use_pager is True:
            click.echo_via_pager(gen_lines)
        else:
            for line in gen_lines:
                click.echo(line, nl=False)
        changes = True
    else:
        click.secho("No changes.", fg="green")
        changes = False
    return changes


@jjm.command(name="plan")
@click.pass_obj
def jjm_plan(obj: JenkinsJobManager):
    """check for changes"""
    check_auth(obj)
    obj.gather()
    changes = handle_plan_report(obj, use_pager=True)
    if changes:
        click.exceptions.Exit(2)


@jjm.command(name="apply")
@click.pass_obj
def jjm_apply(obj: JenkinsJobManager):
    """check and apply changes"""
    check_auth(obj)
    obj.gather()
    if not obj.detected_changes():
        click.secho("No changes to apply.", fg="green")
        return
    handle_plan_report(obj, use_pager=False)
    click.confirm(click.style("Apply changes?", bold=True), abort=True)
    changecounts, msg = obj.apply_plan()
    click.echo(msg)


@jjm.command(name="import")
@click.pass_obj
def jjm_import(obj: JenkinsJobManager):
    check_auth(obj)
    obj.gather()
    missing = obj.import_missing()
    click.secho(f"Imported {len(missing)} jobs.", fg="green")


if __name__ == "__main__":
    jjm()
