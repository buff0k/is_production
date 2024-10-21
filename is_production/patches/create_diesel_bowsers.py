import frappe

def execute():
    # Get the default company configured in ERPNext
    default_company = frappe.db.get_single_value('Global Defaults', 'default_company')
    if not default_company:
        frappe.throw("Default company not found. Please ensure the default company is set in Global Defaults.")

    # Check if the Asset Category with the name 'Diesel Bowsers' already exists
    if not frappe.db.exists('Asset Category', 'Diesel Bowsers'):
        # Get the default Fixed Asset Account for the default company
        fixed_asset_account = frappe.db.get_value('Account', 
            {'company': default_company, 'account_type': 'Fixed Asset', 'root_type': 'Asset'}, 'name')
        
        if not fixed_asset_account:
            frappe.throw(f"Default Fixed Asset Account not found for company {default_company}. Please ensure the account exists.")

        # Create the new Asset Category
        asset_category = frappe.get_doc({
            'doctype': 'Asset Category',
            'asset_category_name': 'Diesel Bowsers',
            'accounts': [{
                'company_name': default_company,
                'fixed_asset_account': fixed_asset_account
            }]
        })
        
        # Insert the document into the database
        asset_category.insert(ignore_permissions=True)
        frappe.msgprint(f"Asset Category 'Diesel Bowsers' created successfully.")
    else:
        frappe.msgprint("Asset Category 'Diesel Bowsers' already exists.")
