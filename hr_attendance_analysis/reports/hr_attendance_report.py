# -*- coding: utf-8 -*-
import math
import pytz
from datetime import time, datetime, timedelta
from openerp import api, models, fields, exceptions
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT


class ParticularReport(models.AbstractModel):
    _name = 'report.hr_attendance_analysis.hr_attendance_analysis_report'

    def _get_day_of_week(self, day):
        WEEKDAYS = {
            0: _('Monday'),
            1: _('Tuesday'),
            2: _('Wednesday'),
            3: _('Thursday'),
            4: _('Friday'),
            5: _('Saturday'),
            6: _('Sunday'),
        }
        weekday = datetime.strptime(day, DEFAULT_SERVER_DATE_FORMAT).weekday()
        return WEEKDAYS[weekday]

    def _get_month_name(self, day):
        str_month = ''
        month = datetime.strptime(day, DEFAULT_SERVER_DATE_FORMAT).month
        if month == 1:
            str_month = _('January')
        elif month == 2:
            str_month = _('February')
        elif month == 3:
            str_month = _('March')
        elif month == 4:
            str_month = _('April')
        elif month == 5:
            str_month = _('May')
        elif month == 6:
            str_month = _('June')
        elif month == 7:
            str_month = _('July')
        elif month == 8:
            str_month = _('August')
        elif month == 9:
            str_month = _('September')
        elif month == 10:
            str_month = _('October')
        elif month == 11:
            str_month = _('November')
        elif month == 12:
            str_month = _('December')
        return str_month

    def _get_year(self, date):
        if date:
            return datetime.strptime(date, DEFAULT_SERVER_DATE_FORMAT).year
        return 0

    @api.multi
    def render_html(self, data=None):
        context = self._context
        if context is None:
            context = {}
        report_obj = self.env['report']
        report = report_obj._get_report_from_name(
            'hr_attendance_analysis.hr_attendance_analysis_report')
        report_param = self.env['attendance_analysis.wizard.calendar_report'].browse(
            context.get('active_id'))
        attendance_pool = self.env['hr.attendance']
        holidays_pool = self.env['hr.holidays']
        precision = self.env['res.users'].browse(
            self.env.user.id).company_id.working_time_precision
        active_tz = pytz.timezone(
            context.get("tz", "UTC") if context else "UTC")

        days_by_employee = {}
        from_date = datetime.strptime(report_param.from_date, '%Y-%m-%d')
        to_date = datetime.strptime(report_param.to_date, '%Y-%m-%d')
        employee_ids = report_param.employee_ids
        delta = to_date - from_date
        max_number_of_attendances_per_day = 0

        for employee_id in employee_ids:
            employee_id = employee_id.id
            days_by_employee[employee_id] = {}
            day_count = 0
            while day_count <= delta.days:
                current_date = from_date + timedelta(day_count)
                current_total_attendances = 0.0
                current_total_overtime = 0.0
                current_total_leaves = 0.0
                # If calendar is not specified: working days = 24/7
                current_total_due = 24.0
                current_total_inside_calendar = 0.0
                str_current_date = current_date.strftime('%Y-%m-%d')
                days_by_employee[employee_id][str_current_date] = {
                    'signin_1': '',
                    'signout_1': '',
                    'signin_2': '',
                    'signout_2': '',
                    'signin_3': '',
                    'signout_3': '',
                    'signin_4': '',
                    'signout_4': '',
                }
                current_date_beginning = datetime.combine(current_date, time())
                current_date_beginning_utc = current_date_beginning.replace(
                    tzinfo=active_tz).astimezone(pytz.utc)
                str_current_date_beginning = (
                    current_date_beginning_utc.strftime('%Y-%m-%d %H:%M:%S'))
                current_date_end = datetime.combine(
                    current_date, time()) + timedelta(1)
                current_date_end_utc = current_date_end.replace(
                    tzinfo=active_tz).astimezone(pytz.utc)
                str_current_date_end = (
                    current_date_end_utc.strftime('%Y-%m-%d %H:%M:%S'))

                attendance_ids = attendance_pool.search([
                    ('employee_id', '=', employee_id),
                    ('name', '>=', str_current_date_beginning),
                    ('name', '<=', str_current_date_end),
                    ('action', '=', 'sign_in')])
                # computing attendance totals
                for attendance in attendance_pool.browse(attendance_ids.id):
                    current_total_attendances = attendance_pool.time_sum(
                        current_total_attendances, attendance.duration)
                    current_total_overtime = attendance_pool.time_sum(
                        current_total_overtime,
                        attendance.outside_calendar_duration)
                    current_total_inside_calendar = attendance_pool.time_sum(
                        current_total_inside_calendar,
                        attendance.inside_calendar_duration)
                # printing up to 4 attendances
                if len(attendance_ids) < 5:
                    count = 1
                    for attendance in sorted(attendance_pool.browse(attendance_ids.id), key=lambda x: x['name']):
                        attendance_start = datetime.strptime(
                            attendance.name, '%Y-%m-%d %H:%M:%S'
                        ).replace(tzinfo=pytz.utc).astimezone(active_tz)
                        attendance_end = datetime.strptime(
                            attendance.end_datetime, '%Y-%m-%d %H:%M:%S'
                        ).replace(tzinfo=pytz.utc).astimezone(active_tz)

                        days_by_employee[employee_id][str_current_date][
                            'signin_'+str(count)] = '%02d:%02d' % (
                            attendance_start.hour, attendance_start.minute)
                        days_by_employee[employee_id][str_current_date][
                            'signout_'+str(count)] = '%02d:%02d' % (
                            attendance_end.hour, attendance_end.minute)
                        count += 1
                    if len(attendance_ids) > max_number_of_attendances_per_day:
                        max_number_of_attendances_per_day = len(attendance_ids)

                days_by_employee[employee_id][str_current_date][
                    'attendances'
                ] = current_total_attendances
                days_by_employee[employee_id][str_current_date][
                    'overtime'
                ] = current_total_overtime

                reference_calendar = attendance_pool.get_reference_calendar(
                    employee_id, date=str_current_date)
                # computing due total
                if reference_calendar:
                    if reference_calendar.attendance_ids:
                        current_total_due = 0.0
                        for calendar_attendance in \
                                reference_calendar.attendance_ids:
                            if (
                                (
                                    not calendar_attendance.dayofweek
                                    or
                                    int(
                                        calendar_attendance.dayofweek
                                    ) == current_date.weekday()
                                )
                                and
                                (
                                    not calendar_attendance.date_from
                                    or
                                    datetime.strptime(
                                        calendar_attendance.date_from,
                                        '%Y-%m-%d'
                                    ) <= current_date
                                )
                            ):
                                calendar_attendance_duration = (
                                    attendance_pool.time_difference(
                                        calendar_attendance.hour_from,
                                        calendar_attendance.hour_to,
                                        help_message=(
                                            'Calendar attendance ID %s'
                                            % calendar_attendance.id))
                                )
                                if calendar_attendance_duration < 0:
                                    raise exceptions.Warning(
                                        _('Error'),
                                        _("%s: 'Work to' is < 'Work from'")
                                        % calendar_attendance.name)
                                current_total_due = \
                                    attendance_pool.time_sum(
                                        current_total_due,
                                        calendar_attendance_duration)
                days_by_employee[employee_id][
                    str_current_date]['due'] = current_total_due
                # computing leaves
                holidays_ids = holidays_pool.search([
                    '&', '&', '|',
                    # leave begins today
                    '&',
                    ('date_from', '>=', str_current_date_beginning),
                    ('date_from', '<=', str_current_date_end),
                    '|',
                    # leave ends today
                    '&',
                    ('date_to', '<=', str_current_date_end),
                    ('date_to', '>=', str_current_date_beginning),
                    # leave is ongoing
                    '&',
                    ('date_from', '<', str_current_date_beginning),
                    ('date_to', '>', str_current_date_end),
                    ('state', '=', 'validate'),
                    ('employee_id', '=', employee_id)])

                for holiday in holidays_pool.browse(holidays_ids.id):
                    date_from = datetime.strptime(
                        holiday.date_from, '%Y-%m-%d %H:%M:%S')
                    date_to = datetime.strptime(
                        holiday.date_to, '%Y-%m-%d %H:%M:%S')
                    # if beginned before today
                    if date_from < current_date_beginning:
                        date_from = current_date_beginning
                    # if ends after today
                    if date_to > current_date_end:
                        date_to = current_date_end
                    date_from = date_from.replace(
                        tzinfo=pytz.utc).astimezone(active_tz)
                    date_to = date_to.replace(
                        tzinfo=pytz.utc).astimezone(active_tz)
                    duration_delta = date_to - date_from
                    duration = (
                        attendance_pool.total_seconds(duration_delta)
                        / 60.0 / 60.0
                    )
                    intervals_within = 0
                    splitted_holidays = (
                        attendance_pool.split_interval_time_by_precision(
                            date_from, duration, precision)
                    )
                    counter = 0
                    for atomic_holiday in splitted_holidays:
                        counter += 1
                        centered_holiday = (
                            attendance_pool.mid_time_interval(
                                atomic_holiday[0],
                                delta=atomic_holiday[1],
                            )
                        )
                        # check if centered_holiday is within a working
                        # schedule
                        weekday_char = str(
                            unichr(centered_holiday.weekday() + 48))
                        matched_schedule_ids = attendance_pool.matched_schedule(
                            centered_holiday,
                            weekday_char,
                            reference_calendar.id
                        )
                        if len(matched_schedule_ids) > 1:
                            raise exceptions.Warning(
                                _('Error'),
                                _('Wrongly configured working schedule with '
                                  'id %s') % str(reference_calendar.id))
                        if matched_schedule_ids:
                            intervals_within += 1

                    current_total_leaves = intervals_within * precision

                days_by_employee[employee_id][str_current_date]['leaves'] = (
                    current_total_leaves)
                if current_total_leaves > days_by_employee[employee_id][
                        str_current_date]['due']:
                    days_by_employee[employee_id][str_current_date][
                        'leaves'
                    ] = days_by_employee[employee_id][str_current_date]['due']
                due_minus_leaves = attendance_pool.time_difference(
                    current_total_leaves, current_total_due,
                    help_message='Employee ID %s. Date %s' % (
                        employee_id, str_current_date))
                if due_minus_leaves < current_total_inside_calendar:
                    days_by_employee[employee_id][
                        str_current_date]['negative'] = 0.0
                else:
                    days_by_employee[employee_id][str_current_date][
                        'negative'
                    ] = attendance_pool.time_difference(
                        current_total_inside_calendar, due_minus_leaves,
                        help_message='Employee ID %s. Date %s' % (
                            employee_id, str_current_date))

                if reference_calendar:
                    if reference_calendar.leave_rounding:
                        float_rounding = float(
                            reference_calendar.leave_rounding)
                        day = days_by_employee[employee_id][str_current_date]
                        day['negative'] = math.floor(
                            day['negative'] * float_rounding) / float_rounding
                day_count += 1
        totals_by_employee = {}
        for employee_id in days_by_employee:
            totals_by_employee[employee_id] = {
                'total_attendances': 0.0,
                'total_overtime': 0.0,
                'total_negative': 0.0,
                'total_leaves': 0.0,
                'total_due': 0.0,
                'total_types': {},
            }
            for str_date in days_by_employee[employee_id]:
                totals_by_employee[employee_id]['total_attendances'] = \
                    attendance_pool.time_sum(
                        totals_by_employee[employee_id]['total_attendances'],
                        days_by_employee[employee_id][str_date]['attendances'])
                totals_by_employee[employee_id]['total_overtime'] = \
                    attendance_pool.time_sum(
                        totals_by_employee[employee_id]['total_overtime'],
                        days_by_employee[employee_id][str_date]['overtime'])
                totals_by_employee[employee_id]['total_negative'] = \
                    attendance_pool.time_sum(
                        totals_by_employee[employee_id]['total_negative'],
                        days_by_employee[employee_id][str_date]['negative'])
                totals_by_employee[employee_id]['total_leaves'] = \
                    attendance_pool.time_sum(
                        totals_by_employee[employee_id]['total_leaves'],
                        days_by_employee[employee_id][str_date]['leaves'])
                totals_by_employee[employee_id]['total_due'] = \
                    attendance_pool.time_sum(
                        totals_by_employee[employee_id]['total_due'],
                        days_by_employee[employee_id][str_date]['due'])
                # computing overtime types
                reference_calendar = attendance_pool.get_reference_calendar(
                    employee_id, date=str_date)
                if reference_calendar:
                    if reference_calendar.overtime_type_ids:
                        sorted_types = sorted(
                            reference_calendar.overtime_type_ids,
                            key=lambda k: k.sequence)
                        current_overtime = days_by_employee[employee_id][
                            str_date]['overtime']
                        for overtime_type in sorted_types:
                            emp = totals_by_employee[employee_id]
                            if not emp['total_types'].get(
                                    overtime_type.name, False):
                                emp['total_types'][overtime_type.name] = 0.0
                            if current_overtime:
                                if current_overtime <= overtime_type.limit or \
                                        not overtime_type.limit:
                                    emp['total_types'][overtime_type.name] = \
                                        attendance_pool.time_sum(
                                            emp['total_types']
                                            [overtime_type.name],
                                            current_overtime)
                                    current_overtime = 0.0
                                else:
                                    emp['total_types'][overtime_type.name] = \
                                        attendance_pool.time_sum(
                                            emp['total_types']
                                            [overtime_type.name],
                                            overtime_type.limit)
                                    current_overtime = \
                                        attendance_pool.time_difference(
                                            overtime_type.limit,
                                            current_overtime)
                days_by_employee[employee_id][str_date][
                    'attendances'
                ] = attendance_pool.float_time_convert(
                    days_by_employee[employee_id][str_date]['attendances'])
                days_by_employee[employee_id][str_date][
                    'overtime'
                ] = attendance_pool.float_time_convert(
                    days_by_employee[employee_id][str_date]['overtime'])
                days_by_employee[employee_id][str_date][
                    'negative'
                ] = attendance_pool.float_time_convert(
                    days_by_employee[employee_id][str_date]['negative'])
                days_by_employee[employee_id][str_date][
                    'leaves'
                ] = attendance_pool.float_time_convert(
                    days_by_employee[employee_id][str_date]['leaves'])
                days_by_employee[employee_id][str_date][
                    'due'
                ] = attendance_pool.float_time_convert(
                    days_by_employee[employee_id][str_date]['due'])
            totals_by_employee[employee_id][
                'total_attendances'
            ] = attendance_pool.float_time_convert(
                totals_by_employee[employee_id]['total_attendances'])
            totals_by_employee[employee_id][
                'total_overtime'
            ] = attendance_pool.float_time_convert(
                totals_by_employee[employee_id]['total_overtime'])
            totals_by_employee[employee_id][
                'total_negative'
            ] = attendance_pool.float_time_convert(
                totals_by_employee[employee_id]['total_negative'])
            totals_by_employee[employee_id][
                'total_leaves'
            ] = attendance_pool.float_time_convert(
                totals_by_employee[employee_id]['total_leaves'])
            totals_by_employee[employee_id][
                'total_due'
            ] = attendance_pool.float_time_convert(
                totals_by_employee[employee_id]['total_due'])
            for overtime_type in \
                    totals_by_employee[employee_id]['total_types']:
                totals_by_employee[employee_id]['total_types'][
                    overtime_type
                ] = attendance_pool.float_time_convert(
                    totals_by_employee[employee_id]['total_types']
                    [overtime_type])
        docargs = {
            'doc_ids': self._ids,
            'doc_model': report.model,
            'docs': self,
            'employee_ids': employee_ids,
            'print_date': fields.datetime.now,
            'days_by_employee': days_by_employee,
            'totals_by_employee': totals_by_employee,
            'day_of_week': self._get_day_of_week,
            'max_per_day': max_number_of_attendances_per_day,
            'month_name': self._get_month_name,
        }
        return report_obj.render('hr_attendance_analysis.hr_attendance_analysis_report', docargs)