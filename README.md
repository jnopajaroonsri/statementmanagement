This is a Django webapp that parses credit card statements and then uses AI to categorize each statement based on description.

The pdfstatement app does all the pdf statement parsing.  It then performs a categorize on the line items within the statement by first looking for existing descriptions in the database,
and then appends the item to a list to send to AI model for categorization.

Users can then either recategorize particular items, all items that match the same description, or move all categories to a different category.

Initial framework is based on common Youtube tutorials and then extended to learn the Django framework along with Python.

For security, we only send a list of descriptions and no other personal information.
