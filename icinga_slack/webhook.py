#!/usr/bin/env python3

import argparse
import json
import urllib.parse
import urllib.request
import sys

from icinga_slack import __version__

alert_colors = {'UNKNOWN': '#6600CC',
                'CRITICAL': '#FF0000',
                'WARNING': '#FF9900',
                'OK': '#36A64F'}

MAX_URL_LENGTH = 22

def abbreviate_url(url):
    parsed_url = urllib.parse.urlparse(url)

    hostname = parsed_url.netloc

    if len(hostname) > MAX_URL_LENGTH:
        hostname = (hostname[:MAX_URL_LENGTH - 2] + '..')

    return "<{0}|{1}>".format(url, hostname)

class AttachmentField(dict):
    def __init__(self, value, title=None, short=False):
        self['value'] = value

        if title:
            self['title'] = title
        self['short'] = short


class AttachmentFieldList(list):
    def __init__(self, *args):
        for count, field in enumerate(args):
            self.append(field)


class Attachment(dict):
    def __init__(self, fallback, fields, mrkdwn_in=[], text=None, pretext=None, color=None):
        self['fallback'] = fallback
        self['mrkdwn_in'] = mrkdwn_in
        self['fields'] = fields
        if text:
            self['text'] = text
        if pretext:
            self['pretext'] = pretext
        if color:
            self['color'] = color


class AttachmentList(list):
    def __init__(self, *args):
        for count, attachment in enumerate(args):
            self.append(attachment)


class Message(dict):
    def __init__(self, channel, text, username,
                 icon_emoji=":ghost:", attachments=None):
        self['channel'] = channel
        self['text'] = text
        if username:
            self['username'] = username
        if icon_emoji:
            self['icon_emoji'] = icon_emoji
        self['attachments'] = AttachmentList()

    def attach(
            self,
            message,
            level,
            host = None,
            host_display_name = None,
            action_url=None,
            notes_url=None,
            status_cgi_url='',
            extinfo_cgi_url=''
    ):
        fields = AttachmentFieldList()

        host_and_service_text = []
        if host and extinfo_cgi_url:
            host_and_service_text.append(
                "*Service:* " + abbreviate_url(
                    "{0}?type=2&host={1}&service={2}".format(
                        extinfo_cgi_url,
                        host,
                        message
                    )
                )
            )

        if host_display_name or host:
            host_and_service_text.append(
                "*Host:* " +  abbreviate_url("{0}?host={1}".format(
                    status_cgi_url,
                    host_display_name
                ))
            )

        fields.append(
            AttachmentField(
                "\n".join(host_and_service_text),
                short=True
            )
        )

        links_text = []
        if action_url:
            links_text.append(
                "*Action:* {0}".format(abbreviate_url(action_url))
            )
        if notes_url:
            links_text.append(
                "*Notes:* {0}".format(abbreviate_url(notes_url))
            )
        fields.append(
            AttachmentField(
                "\n".join(links_text),
                short=True
            )
        )
        if level in alert_colors.keys():
            color = alert_colors[level]
        else:
            color = alert_colors['UNKNOWN']
        alert_attachment = Attachment(
            fallback="    {0} on {1} is {2}".format(message, host_display_name, level),
            mrkdwn_in=['fields'],
            color=color,
            fields=fields
        )
        self['attachments'].append(alert_attachment)

    def send(self, webhook_url):
        data = urllib.parse.urlencode({"payload": json.dumps(self)})
        response = urllib.request.urlopen(
            webhook_url,
            data.encode('utf8')
        ).read()
        if response == b'ok':
            return True
        else:
            print("Error: %s" % response)
            return False


def parse_options():
    parser = argparse.ArgumentParser(
        prog="icinga_slack_webhook_notify",
        description="Send an Icinga Alert to Slack.com via a generic webhook integration"
    )
    parser.add_argument(
        '-c', '--channel',
        required=True,
        help="The channel to send the message to"
    )
    parser.add_argument(
        '-m', '--message',
        required=True,
        help="The text of the message to send"
    )
    destination_group = parser.add_mutually_exclusive_group()
    destination_group.add_argument(
        '-u', '--web-hook-url',
        help="The webhook URL for your integration"
    )
    destination_group.add_argument(
        '-p', '--print-payload',
        action='store_const',
        const=True,
        default=False,
        help="Rather than sending the payload to Slack, print it to STDOUT"
    )
    parser.add_argument(
        '-A', '--service-action-url',
        default=None,
        help="An optional action_url for this alert {default: None}"
    )
    parser.add_argument(
        '-H', '--host',
        help="An optional host the message relates to"
    )
    parser.add_argument(
        '-d', '--host-display-name',
        help="An optional display name for the host the message relates to"
    )
    parser.add_argument(
        '-L', '--level',
        choices=["OK", "WARNING", "CRITICAL", "UNKNOWN"],
        default="UNKNOWN",
        help="An optional alert level {default: UNKNOWN}"
    )
    parser.add_argument(
        '-N', '--service-notes-url',
        default=None,
        help="An optional notes_url for this alert {default: None}"
    )
    parser.add_argument(
        '-S', '--status-cgi-url',
        default='https://nagios.example.com/cgi-bin/icinga/status.cgi',
        help="The URL of status.cgi for your Nagios/Icinga instance {default: https://nagios.example.com/cgi-bin/icinga/status.cgi}"
    )
    parser.add_argument(
        '-E', '--extinfo-cgi-url',
        help="The URL of extinfo.cgi for your Nagios/Icinga instance"
    )
    parser.add_argument(
        '-U', '--username',
        default="Icinga",
        help="Username to send the message from {default: Icinga}"
    )
    parser.add_argument(
        '-V', '--version',
        action='version',
        help="Print version information",
        version=__version__
    )

    return parser.parse_args()


def main():
    args = parse_options()
    message = Message(
        channel=args.channel,
        text="*{0}*: {1}".format(args.level, args.message),
        username=args.username
    )
    message.attach(
        message=args.message,
        host=args.host,
        host_display_name=args.host_display_name,
        level=args.level,
        action_url=args.service_action_url,
        notes_url=args.service_notes_url,
        status_cgi_url=args.status_cgi_url,
        extinfo_cgi_url=args.extinfo_cgi_url
    )

    if args.print_payload:
        print(json.dumps(message, indent=True))
    else:
        if message.send(webhook_url=args.web_hook_url):
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
