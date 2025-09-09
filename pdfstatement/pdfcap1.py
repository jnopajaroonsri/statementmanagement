import re, pdb, logging
from datetime import datetime
from PyPDF2 import PdfReader

def parsecap1pdf(url):
    logger = logging.getLogger(__name__)

    parse_transactions = False
    date_needs_parse = True
    pdf = PdfReader(url)
    transaction_count = 0
    transaction_list = []
    totalBalance = 0.00

    for page in pdf.pages:
        pdf_text = page.extract_text()

        line_number = 0
        for line in pdf_text.split('\n'):
            print(line, flush=True)
            line_number += 1
            if re.search(r"^Transactions", line):
                parse_transactions = False
                continue
            if re.search(r"Trans Date Post Date Description Amount", line):
                parse_transactions = True
                continue

            if date_needs_parse and re.search(r"days in Billing Cycle", line):
                # Jun 13, 2025 - Jul 13, 2025
                print(line, flush=True)
                period_string = line.split("|")[0]
                start_date_string, end_date_string = period_string.strip().split("-")
                start_date = datetime.strptime(start_date_string.strip(), "%b %d, %Y")
                end_date = datetime.strptime(end_date_string.strip(), "%b %d, %Y")
                statement_year = start_date.year
                statement_range = start_date.strftime("%Y/%m/%d") + " to " + end_date.strftime("%Y/%m/%d")
                date_needs_parse = False
                continue

            if re.search(r"^Total Transactions for This Period", line):
                totalBalance = line.split("$")[1].replace(",", '')
                continue

            # cap1
            data = re.search(r"(\w+\s\d+)\s+(\w+\s\d+)\s+([\w\s#*&!?'.()\/-]+)\s+(\$[\d.]+)", line)
            if parse_transactions == True and data:
                payment_data = re.search(r"(\w+\s\d+)\s+(\w+\s\d+)\s+([\w\s#*&!?'.()\/-]+)\s+(-\s\$[\d.]+)", line)
                transaction_date = datetime.strptime(data[1], "%b %d")
                posting_date = datetime.strptime(data[2], "%b %d")
                if transaction_date.month == start_date.month:
                    transaction_date = transaction_date.replace(year=start_date.year)
                    posting_date = posting_date.replace(year=start_date.year)
                else:
                    transaction_date = transaction_date.replace(year=end_date.year)
                    posting_date = posting_date.replace(year=end_date.year)
                if payment_data:
                    amount = payment_data[4].replace(" $", '')
                else:
                    amount = data[4].replace("$", '')
                transaction_list.append({
                    'transactionDate': transaction_date,
                    'postingDate': posting_date,
                    'description': data[3],
                    'transactionId': transaction_count,
                    'account_number': '',
                    'amount': amount
                })
                transaction_count += 1
                continue

    return(transaction_list, statement_range, totalBalance)