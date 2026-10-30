# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import time
from odoo import api, models, _
from odoo.exceptions import UserError


class ReportFinancial(models.AbstractModel):
    _name = 'report.base_accounting_kit.report_cash_flow'
    _description = 'Cash Flow Report'

    # ------------------------------------------------------------------
    # Odoo 19 fixes (MyMealsKost thesis):
    #  * account.account has company_ids, not company_id.
    #  * The original 'sum' and 'accounts' branches summed the accounts of
    #    the parent report, which is always empty, so every line was 0.
    #  * Direct method: a cash movement is a posted journal entry that
    #    touches a liquidity (bank/cash) account. Each non-liquidity line of
    #    such an entry is the counterpart. The counterpart account is
    #    classified through the existing "Cash Flow type" field and lands
    #    in the Cash In / Cash Out node of Operations, Investing or
    #    Financing. Anything not classified is shown as a difference line.
    # ------------------------------------------------------------------

    def _liquidity_accounts(self):
        return self.env['account.account'].search(
            [('account_type', '=', 'asset_cash')])

    def _period_domain(self):
        ctx = self.env.context
        if ctx.get('state') == 'posted':
            domain = [('parent_state', '=', 'posted')]
        else:
            domain = [('parent_state', 'in', ('posted', 'draft'))]
        if ctx.get('date_from'):
            domain.append(('date', '>=', ctx['date_from']))
        if ctx.get('date_to'):
            domain.append(('date', '<=', ctx['date_to']))
        if ctx.get('journal_ids'):
            domain.append(('journal_id', 'in', ctx['journal_ids']))
        if ctx.get('company_id'):
            domain.append(('company_id', '=', ctx['company_id']))
        return domain

    def _compute_account_balance(self, accounts):
        """Debit/credit of the counterpart lines of each classified account,
        counting only journal entries that also touch a liquidity account."""
        res = {}
        for account in accounts:
            res[account.id] = {'debit': 0.0, 'credit': 0.0, 'balance': 0.0}
        liquidity = self._liquidity_accounts()
        if accounts and liquidity:
            domain = [
                ('account_id', 'in', accounts.ids),
                ('move_id.line_ids.account_id', 'in', liquidity.ids),
            ] + self._period_domain()
            groups = self.env['account.move.line']._read_group(
                domain, groupby=['account_id'],
                aggregates=['debit:sum', 'credit:sum'])
            for account, debit, credit in groups:
                res[account.id] = {'debit': debit, 'credit': credit,
                                   'balance': debit - credit}
        return res

    def _node_direction(self, report):
        cash_in = [self.env.ref('base_accounting_kit.' + x) for x in (
            'cash_in_from_operation0', 'cash_in_investing0',
            'cash_in_financial0')]
        cash_out = [self.env.ref('base_accounting_kit.' + x) for x in (
            'cash_out_operation1', 'cash_out_investing1',
            'cash_out_financial1')]
        if report in cash_in:
            return 'in'
        if report in cash_out:
            return 'out'
        return False

    def _compute_report_balance(self, reports):
        res = {}
        fields = ['credit', 'debit', 'balance']
        for report in reports:
            if report.id in res:
                continue
            res[report.id] = dict((fn, 0.0) for fn in fields)
            if report.type == 'accounts':
                direction = self._node_direction(report)
                per_account = self._compute_account_balance(report.account_ids)
                accounts_res = {}
                for acc_id, val in per_account.items():
                    if direction == 'in':
                        # cash received: counterpart credit, refunds: debit
                        row = {'debit': val['credit'], 'credit': val['debit']}
                    elif direction == 'out':
                        # cash paid: counterpart debit (shown as credit and a
                        # negative balance), refunds: counterpart credit
                        row = {'debit': val['credit'], 'credit': val['debit']}
                    else:
                        row = {'debit': 0.0, 'credit': 0.0}
                    row['balance'] = row['debit'] - row['credit']
                    accounts_res[acc_id] = row
                    for field in fields:
                        res[report.id][field] += row[field]
                res[report.id]['account'] = accounts_res
            elif report.type == 'sum':
                # a section is the sum of its child reports
                children = self._compute_report_balance(report.children_ids)
                for value in children.values():
                    for field in fields:
                        res[report.id][field] += value[field]
        return res

    def _cash_summary_lines(self, root_balance, debit_credit, enable_filter):
        """Reconciliation lines that make the cash movement traceable."""
        liquidity = self._liquidity_accounts()
        AML = self.env['account.move.line']
        ctx = self.env.context
        net = 0.0
        for debit, credit in AML._read_group(
                [('account_id', 'in', liquidity.ids)] + self._period_domain(),
                aggregates=['debit:sum', 'credit:sum']):
            net = (debit or 0.0) - (credit or 0.0)
        opening = 0.0
        if ctx.get('date_from'):
            odom = [('account_id', 'in', liquidity.ids),
                    ('date', '<', ctx['date_from']),
                    ('parent_state', '=', 'posted')]
            if ctx.get('company_id'):
                odom.append(('company_id', '=', ctx['company_id']))
            for debit, credit in AML._read_group(
                    odom, aggregates=['debit:sum', 'credit:sum']):
                opening = (debit or 0.0) - (credit or 0.0)
        rows = [
            ('Net increase (decrease) in cash per classification',
             root_balance),
            ('Net movement of Bank/Cash accounts', net),
            ('Unclassified cash movement (classify more accounts if not 0)',
             net - root_balance),
            ('Opening cash balance', opening),
            ('Closing cash balance', opening + net),
        ]
        lines = []
        for name, value in rows:
            vals = {'name': name, 'balance': value, 'type': 'report',
                    'level': 1, 'account_type': False}
            if debit_credit:
                vals['debit'] = 0.0
                vals['credit'] = 0.0
            if enable_filter:
                vals['balance_cmp'] = 0.0
            lines.append(vals)
        return lines

    def get_account_lines(self, data):
        lines = []
        account_report = self.env['account.financial.report'].search(
            [('id', '=', data['account_report_id'][0])])
        child_reports = account_report._get_children_by_order()
        res = self.with_context(
            data.get('used_context'))._compute_report_balance(child_reports)
        if data['enable_filter']:
            comparison_res = self.with_context(
                data.get('comparison_context'))._compute_report_balance(
                child_reports)
            for report_id, value in comparison_res.items():
                res[report_id]['comp_bal'] = value['balance']
                report_acc = res[report_id].get('account')
                if report_acc:
                    for account_id, val in comparison_res[report_id].get(
                            'account').items():
                        report_acc[account_id]['comp_bal'] = val['balance']

        for report in child_reports:
            vals = {
                'name': report.name,
                'balance': res[report.id]['balance'] * int(report.sign),
                'type': 'report',
                'level': bool(report.style_overwrite) and int(
                    report.style_overwrite) or report.level,
                'account_type': report.type or False,
                # used to underline the financial report balances
            }
            if data['debit_credit']:
                vals['debit'] = res[report.id]['debit']
                vals['credit'] = res[report.id]['credit']

            if data['enable_filter']:
                vals['balance_cmp'] = res[report.id]['comp_bal'] * int(
                    report.sign)

            lines.append(vals)
            if report.display_detail == 'no_detail':
                # the rest of the loop is used to display the details of the financial report, so it's not needed here.
                continue
            if res[report.id].get('account'):
                sub_lines = []
                for account_id, value in res[report.id]['account'].items():
                    # if there are accounts to display, we add them to the
                    # lines with a level equals to their level in
                    # the COA + 1 (to avoid having them with a too low level
                    # that would conflicts with the level of data
                    # financial reports for Assets, liabilities...)
                    flag = False
                    account = self.env['account.account'].browse(account_id)
                    vals = {
                        'name': account.code + ' ' + account.name,
                        'balance': value['balance'] * int(report.sign) or 0.0,
                        'type': 'account',
                        'level': report.display_detail == 'detail_with_hierarchy' and 4,
                        'account_type': account.account_type,
                    }
                    # Odoo 19: account.account uses company_ids (many2many),
                    # not company_id, same fix as wizard/financial_report.py
                    if data['debit_credit']:
                        vals['debit'] = value['debit']
                        vals['credit'] = value['credit']
                        for company in account.company_ids:
                            if not company.currency_id.is_zero(
                                    vals['debit']) or \
                                    not company.currency_id.is_zero(
                                        vals['credit']):
                                flag = True
                    for company in account.company_ids:
                        if not company.currency_id.is_zero(vals['balance']):
                            flag = True
                    if data['enable_filter']:
                        vals['balance_cmp'] = value['comp_bal'] * int(
                            report.sign)
                        for company in account.company_ids:
                            if not company.currency_id.is_zero(
                                    vals['balance_cmp']):
                                flag = True
                    if flag:
                        sub_lines.append(vals)
                lines += sorted(sub_lines,
                                key=lambda sub_line: sub_line['name'])
        root = child_reports[:1]
        if root and not root.parent_id:
            lines += self.with_context(
                data.get('used_context'))._cash_summary_lines(
                res[root.id]['balance'], data['debit_credit'],
                data['enable_filter'])
        return lines

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data.get('form') or not self.env.context.get(
                'active_model') or not self.env.context.get('active_id'):
            raise UserError(
                _("Form content is missing, this report cannot be printed."))

        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_id'))
        report_lines = self.get_account_lines(data.get('form'))
        return {
            'doc_ids': self.ids,
            'doc_model': model,
            'data': data['form'],
            'docs': docs,
            'time': time,
            'get_account_lines': report_lines,
        }
