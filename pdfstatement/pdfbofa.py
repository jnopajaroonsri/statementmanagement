import re, pdb, logging, datetime
from PyPDF2 import PdfReader
from django.conf import settings

def parsebofapdf(url):
    logger = logging.getLogger(__name__)
    parse_transactions = False
    parse_statement_range = False
    pdf = PdfReader(url)
    transaction_count = 0
    transaction_list = []
    totalBalance = 0.00

    for page in pdf.pages:
        pdf_text = page.extract_text()

        line_number = 0
        for line in pdf_text.split('\n'):
            line_number += 1
            if re.search(r"^Account\#", line):
                parse_statement_range = True
                continue

            if re.search(r"^Transaction", line):
                parse_transactions = True
                continue

            if re.search(r"^New Balance Total", line):
                totalBalance = re.search(r"\$([-\d.,]+)", line)[1].replace(",", '')
                continue

            if parse_statement_range:
                # July 6 - August 5, 2025
                start_month, end_date = line.strip().split("-")
                end_month, end_statement_year = end_date.strip().split(",")
                
                # calculate start year, in the event that end month is in January
                end_date = datetime.datetime.strptime(end_month + " " + end_statement_year.strip(), "%B %d %Y")
                statement_year = str(int(end_statement_year.strip(), base=10) - 1) if re.search('January', end_month) else end_statement_year
                start_date = datetime.datetime.strptime(start_month + " " + statement_year.strip(), "%B %d %Y")

                statement_range = start_date.strftime("%Y/%m/%d") + " to " + end_date.strftime("%Y/%m/%d")
                parse_statement_range = False
                continue

            # bofa regex
            data = re.search(r"(\d+\/\d+)\s+(\d+\/\d+)\s+([\w\s\/#*&!?'.()-]+)\s+(\d{4})\s+(\d{4})\s+([-$\d.,]+)", line)
            if parse_transactions == True and data:
                print(data, flush=True)
                transaction_date = datetime.datetime.strptime(data[1].replace("/", "-"), "%m-%d")
                posting_date = datetime.datetime.strptime(data[2].replace("/", "-"), "%m-%d")
                if transaction_date.month == start_date.month:
                    transaction_date = transaction_date.replace(year=start_date.year)
                    posting_date = posting_date.replace(year=start_date.year)
                else:
                    transaction_date = transaction_date.replace(year=end_date.year)
                    posting_date = posting_date.replace(year=end_date.year)
                transaction_list.append({
                    'transactionDate': transaction_date,
                    'postingDate': posting_date,
                    'description': data[3],
                    'transactionId': data[4],
                    'account_number': data[5],
                    'amount': data[6].replace(",",'').replace("$", '')
                })
                transaction_count += 1
                continue

    return(transaction_list, statement_range, totalBalance)
