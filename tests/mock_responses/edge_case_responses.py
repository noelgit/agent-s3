# tests/mock_responses/edge_case_responses.py

# Edge Case Responses
EDGE_CASE_RESPONSES = {
    # Empty Implementation
    "empty_implementation": {
        "planning": {
            "create_plan": """
            # No Implementation Required

            ## Overview
            After analyzing the request, no implementation is required because the requested functionality already exists.

            ## Explanation
            The requested feature already exists in the codebase. The desired functionality is provided by the module at `utils/existing.py`.

            ## Recommendation
            Use the existing implementation instead of creating a new one. Here's an example of how to use it:

            ```python
            from utils.existing import feature_function

            result = feature_function(param1, param2)
            ```
            """
        },
        "code_generation": {
            "code": {}  # No code needed
        }
    },

    # Partial Implementation
    "partial_implementation": {
        "planning": {
            "create_plan": """
            # Partial Implementation Plan: Add CSV Export Feature

            ## Overview
            Implement CSV export for the data report feature. Part of the functionality already exists.

            ## What Already Exists
            The `export.py` module already contains functionality for exporting data to JSON and XML.

            ## What's Missing
            The CSV export function needs to be added to complete the export functionality.

            ## Files to Modify
            - `utils/export.py` - Add CSV export function
            - `tests/test_export.py` - Add tests for CSV export

            ## Implementation Notes
            Use the existing `_prepare_data` helper function for data preparation before export.
            """
        },
        "code_generation": {
            "code": {
                "utils/export.py": '''
                def export_to_csv(data, filepath, delimiter=','):
                    """Export data to CSV file.

                    Args:
                        data: List of dictionaries to export
                        filepath: Path to save the CSV file
                        delimiter: CSV delimiter character

                    Returns:
                        True if export successful, False otherwise
                    """
                    if not data:
                        return False

                    # Prepare data using existing helper
                    prepared_data = _prepare_data(data)

                    try:
                        import csv

                        # Get fieldnames from the first row
                        fieldnames = list(prepared_data[0].keys())

                        with open(filepath, 'w', newline='') as csvfile:
                            writer = csv.DictWriter(
                                csvfile,
                                fieldnames=fieldnames,
                                delimiter=delimiter
                            )

                            # Write header and rows
                            writer.writeheader()
                            writer.writerows(prepared_data)

                        return True
                    except Exception as e:
                        logger.error("%s", CSV export error: {str(e)})
                        return False
                '''
            }
        }
    }
}
