# -*- coding: utf-8 -*-
from openerp import api, models, fields


class HrAttendanceAnalysisReport(models.TransientModel):
    _name = "attendance_analysis.wizard.calendar_report"
    _description = "Attendance Analysis Reporting Wizard"

    from_date = fields.Date('From Date', required=True)
    to_date = fields.Date('To Date', required=True)
    employee_ids = fields.Many2many(
        'hr.employee', 'calendar_report_employee_rel', 'employee_id',
        'report_id', required=True)

    @api.multi
    def action_print(self):
        [data] = self.read()
        datas = {
            'ids': self.env.context.get('active_ids', []),
            'model': 'hr.employee',
            'form': data
        }
        return self.env['report'].get_action(self, 'hr_attendance_analysis.hr_attendance_analysis_report', data=datas)