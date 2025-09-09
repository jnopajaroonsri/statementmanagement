import pdfreader, subprocess, re, logging, datetime
from pdfreader import PDFDocument, SimplePDFViewer

# WF statements with currency conversions do not parse correctly with PyPdf2.
# the ordering of the conversion lines are inset tables which throw off the line by line processing
# instead, we use pdfreader here, which returns each element in order it is found.

# we use flags to determine state of what kind of processing we need to do if we encounter fields that need to be skipped.
# the expectation is that the pdfreader will return a long list of elements in order. the typical transaction will be 8 items long.
# however, transaction with a conversion fee will be 12 items long, which includes 4 items interspersed within the 12 items.
# we need to skip the lines that correspond to the conversion fee info.
def parsewfpdf(url):
    logger = logging.getLogger(__name__)

    parse_transactions = False
    viewer = SimplePDFViewer(url)
    transaction_count = 0
    transactions_flag = False
    fees_charged_flag = False
    total_charges_flag = False
    viewer.navigate(3)
    viewer.render()
    transaction_line = []
    transaction_list = []
    field_max = 6
    field_captured = 0
    account_number = None
    skip_line_count = 0
    totalBalance = 0
    catch_line_after_skip = False

    for string in viewer.canvas.strings:
        # begin transaction processing
        if re.search(r"Purchases, Balance Transfers & Other Charges", string):
            transactions_flag = True
            continue
        # stop transaction processing and begin fees processing
        elif re.search(r"^Fees Charged", string):
            transaction_line = []
            field_captured = 0
            fees_charged_flag = True
            continue
        # grab statement period
        elif re.search(r"^Statement Period", string):
            # Statement Period 06/18/2025 to 07/18/2025
            split_string = string.split(" ")
            start_date = datetime.datetime.strptime(split_string[2], "%m/%d/%Y")
            end_date = datetime.datetime.strptime(split_string[4], "%m/%d/%Y")
            statement_year = start_date.year
            statement_range = start_date.strftime("%Y/%m/%d") + " to " + end_date.strftime("%Y/%m/%d")
            continue
        # grab total on next line
        elif re.search(r"^TOTAL PURCHASES, BALANCE TRANSFERS & OTHER CHARGES FOR THIS PERIOD", string):
            print(string, flush=True)
            total_charges_flag = True
            continue
        # actually grab total
        elif total_charges_flag:
            print(string, flush=True)
            totalBalance = string.strip().replace("$", '').replace(",", '')
            total_charges_flag = False
            continue
        # transaction processing here
        elif transactions_flag == True and field_captured < field_max:
            # first time through, we need to set the account_number
            if not account_number and field_captured == 0:
                account_number = string
            
            # TBD - data set is a single page
            # if we're expecting the beginning of a transaction, but the string doesn't match, 
            # we might be done with processing, so stop transactions processing
            if field_captured == 0 and not account_number == string:
                transactions_flag = False
                continue
            
            # if the item begins with -, we may have encountered a conversion fee line, so count it then skip to next item
            if re.search(r"^-\s+", string):
                skip_line_count += 1
                catch_line_after_skip = True
                continue

            # we get here ONLY if we hit a line after skipping conversion lines.
            if catch_line_after_skip:
                transaction_line.append(string)
                field_captured += 1
                catch_line_after_skip = False
                continue

            # this will skip the corresponding fields to the skip line
            if skip_line_count > 0:
                skip_line_count -= 1
                continue

            # normal processing occurs here: add the item to the transaction_line list and increment the counter
            transaction_line.append(string)
            field_captured += 1

            # when we reach the capture amount equal to the max, we finish the transaction line and reset it and the counter
            if field_captured == field_max:
                transaction_date = datetime.datetime.strptime(transaction_line[1].replace("/", "-"), "%m-%d")
                posting_date = datetime.datetime.strptime(transaction_line[2].replace("/", "-"), "%m-%d")
                if transaction_date.month == start_date.month:
                    transaction_date = transaction_date.replace(year=start_date.year)
                    posting_date = posting_date.replace(year=start_date.year)
                else:
                    transaction_date = transaction_date.replace(year=end_date.year)
                    posting_date = posting_date.replace(year=end_date.year)
                transaction_list.append({
                    'account_number': transaction_line[0],
                    'transactionDate': transaction_date,
                    'postingDate': posting_date,
                    'transactionId': transaction_line[3] + str(transaction_count),
                    'description': transaction_line[4],
                    'amount': transaction_line[5]
                })
                transaction_count += 1
                transaction_line = []
                field_captured = 0
            continue
        # begin fees processing here
        elif fees_charged_flag == True and field_captured < field_max:
            if field_captured == 0 and not account_number == string:
                fees_charged_flag = False
                continue

            transaction_line.append(string)
            field_captured += 1
            
            if field_captured == field_max:
                transaction_date = datetime.datetime.strptime(transaction_line[1].replace("/", "-"), "%m-%d")
                posting_date = datetime.datetime.strptime(transaction_line[2].replace("/", "-"), "%m-%d")
                if transaction_date.month == start_date.month:
                    transaction_date = transaction_date.replace(year=start_date.year)
                    posting_date = posting_date.replace(year=start_date.year)
                else:
                    transaction_date = transaction_date.replace(year=end_date.year)
                    posting_date = posting_date.replace(year=end_date.year)
                transaction_list.append({
                    'account_number': transaction_line[0],
                    'transactionDate': transaction_date,
                    'postingDate': posting_date,
                    'transactionId': 'F' + transaction_line[3] + str(transaction_count),
                    'description': transaction_line[4],
                    'amount': transaction_line[5]
                })
                transaction_count += 1
                transaction_line = []
                field_captured = 0
                continue

    return(transaction_list, statement_range, totalBalance)