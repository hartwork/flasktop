#! /usr/bin/env python3
# "top in the browser"
# Makes use of Flask and jQuery DataTables
#
# Copyright (C) 2016 Sebastian Pipping <sebastian@pipping.org>
# Licensed under GNU /Affero/ General Public License v3 or later

import json
from textwrap import dedent

import psutil
from flask import Flask


_STATUS_HUMAN = {
    psutil.STATUS_RUNNING: 'running',
    psutil.STATUS_SLEEPING: 'sleeping',
    psutil.STATUS_DISK_SLEEP: 'disk-sleep',
    psutil.STATUS_STOPPED: 'stopped',
    psutil.STATUS_TRACING_STOP: 'tracing-stop',
    psutil.STATUS_ZOMBIE: 'zombie',
    psutil.STATUS_DEAD: 'dead',
    psutil.STATUS_WAKING: 'waking',
    psutil.STATUS_IDLE: 'idle',
    psutil.STATUS_LOCKED: 'locked',
    psutil.STATUS_WAITING: 'waiting',
}

_app = Flask(__name__)

_cpu_percent_prev = {}


@_app.route("/data")
def _data():
    rows = []
    for p in psutil.process_iter():
        try:
            cpu_time_user, cpu_time_system, _, _ = p.cpu_times()
            mi = p.memory_info()

            cpu_percent = p.cpu_percent()
            cpu_percent_slow = (cpu_percent + _cpu_percent_prev.get(p.pid, cpu_percent)) / 2
            _cpu_percent_prev[p.pid] = cpu_percent_slow  # TODO: clean cache

            d = {
                'pid': p.pid,
                'name': p.name(),
                'exe': p.exe(),
                'cmdline': ' '.join(p.cmdline()),
                'username': p.username(),
                'num_fds': p.num_fds(),
                'num_threads': p.num_threads(),
                'cpu_time_user': cpu_time_user,
                'cpu_time_system': cpu_time_system,
                'rss': mi.rss,
                'vms': mi.vms,
                'cpu_percent': cpu_percent,
                'cpu_percent_slow': cpu_percent_slow,
                'status': _STATUS_HUMAN.get(p.status()),
            }
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

        rows.append(d)

    return json.dumps(rows, indent=2, sort_keys=True)


@_app.route("/")
def _index():
    return dedent("""
        <html>
            <head>
                <title>AjaxTop</title>

                <link rel="stylesheet" type="text/css"
                    href="https://cdn.datatables.net/v/dt/jq-2.2.3/dt-1.10.12/datatables.min.css"/>
                <script type="text/javascript"
                    src="https://cdn.datatables.net/v/dt/jq-2.2.3/dt-1.10.12/datatables.min.js">
                </script>

                <style type="text/css">
                    /* Datatables tuning */
                    div#processes_info {
                        display: none;
                    }

                    table.dataTable thead th, table.dataTable thead td {
                        // border-bottom: none;
                    }

                    table.dataTable.no-footer {
                        border-bottom: none;
                    }

                    table.dataTable thead tr {
                        background-color: #e0e0e0;
                    }

                    /* Our own classes */
                    table#processes tr.running0 td {
                        color: #000000;
                        background-color: #ffffa0;
                    }
                    table#processes tr.running20 td {
                        color: #000000;
                        background-color: #e0e000;
                    }
                    table#processes tr.running80 td {
                        color: #000000;
                        background-color: #ff0000;
                    }
                </style>

                <script type="text/javascript">
                    $(document).ready( function () {
                        var formatInt = function ( data, type, row ) {
                            return data.toString().replace( /\B(?=(\d{3})+(?!\d))/g, ',' );
                        }

                        var formatFloat = function ( data, type, row ) {
                            if (data > 0) {
                                data = Math.max(data, 0.01)
                            }
                            return data.toFixed(2)
                        }

                        var formatDuration = function ( data, type, row ) {
                            hours = Math.floor(data / 3600)
                            data -= hours * 3600

                            minutes = Math.floor(data / 60)
                            data -= minutes * 60

                            seconds = Math.max(Math.ceil(data), 1)

                            minutes_padded = ((minutes < 10) ? '0' : '') + minutes
                            seconds_padded = ((seconds < 10) ? '0' : '') + seconds
                            full = hours + ':' + minutes_padded + ':' + seconds_padded

                            return full.replace( /^[0:]+/, '' )
                        }

                        var processes = $('#processes').dataTable({
                            ajax: {
                                url: '/data',
                                dataSrc: ''
                            },
                            columns: [
                                { title: 'ID', data: 'pid',
                                    className: 'dt-right' },
                                { title: 'Status', data: 'status' },
                                { title: 'Name', data: 'name' },
                                { title: '%CPU', data: 'cpu_percent_slow',
                                    className: 'dt-right', render: formatFloat },
                                { title: 'User time', data: 'cpu_time_user',
                                    className: 'dt-right', render: formatDuration },
                                { title: 'Sys time', data: 'cpu_time_system',
                                    className: 'dt-right', render: formatDuration },
                                { title: 'RSS', data: 'rss',
                                    className: 'dt-right', render: formatInt },
                                { title: 'VMS', data: 'vms',
                                    className: 'dt-right', render: formatInt },
                                { title: 'User', data: 'username' },
                                { title: 'Command', data: 'cmdline' },
                                { title: 'Exe', data: 'exe' },
                                { title: '#Files', data: 'num_fds',
                                    className: 'dt-right' },
                                { title: '#Threads', data: 'num_threads',
                                    className: 'dt-right' }
                            ],
                            order: [
                                [ 3, 'desc' ],  // %CPU
                                [ 2, 'asc' ],  // Name
                                [ 0, 'asc' ],  // ID
                            ],
                            paging: false,
                            fnCreatedRow: function( nRow, aData, iDataIndex ) {
                                cpu = aData['cpu_percent_slow']
                                if ((aData['status'] == 'running') || (cpu > 0)) {
                                    if (cpu >= 80) {
                                        className = 'running80';
                                    } else if (cpu >= 20) {
                                        className = 'running20';
                                    } else {
                                        className = 'running0';
                                    }

                                    $(nRow).addClass(className);
                                }

                                title = $('td:eq(2)', nRow)
                                title.html( '<strong>' + title.html() + '</strong>' )

                                cmdline = $('td:eq(9)', nRow)
                                cmdline.html( cmdline.html().replace( /([^\/ ]+)( |$)/, '<strong>$1</strong>$2' ) )

                                exe = $('td:eq(10)', nRow)
                                exe.html( exe.html().replace( /[^\/]+$/, '<strong>$&</strong>' ) )
                            },
                            fnFooterCallback: function( nFoot, aData, iStart, iEnd, aiDisplay ) {
                                // console.log(nFoot, aData, iStart, iEnd, aiDisplay);
                            },
                        });

                        reload = function () {
                            processes.api().ajax.reload( null, false );
                        }

                        setTimeout( reload, 500 );
                        setInterval( reload, 2000 );
                    } );
                </script>
            </head>
            <body>
                <table id="processes" class="stripe hover order-column nowrap compact">
                </table>
            </body>
        </html>
    """)


if __name__ == "__main__":
    _app.run()
