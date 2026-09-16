import os
import sys
import logging
import subprocess
import shutil
import tempfile
import json
from pathlib import Path

# ==============================================================================
# CONFIGURATION - This PY convert all excel files in subfolders to PDF
# ==============================================================================

# Excel file extensions to process
EXCEL_EXTENSIONS = ['.xlsx', '.xls', '.xlsm']

# ==============================================================================
# Script Implementation
# ==============================================================================

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('excel_to_pdf_converter')

def natural_sort_key(s):
    """Sort strings with embedded numbers in natural order."""
    import re
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', str(s))]

def check_libreoffice():
    """Check if LibreOffice is installed and find the executable."""
    possible_commands = [
        'libreoffice',
        'soffice',
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
        '/usr/bin/libreoffice',
        '/usr/local/bin/libreoffice',
        '/opt/libreoffice/program/soffice'
    ]
    
    for cmd in possible_commands:
        if shutil.which(cmd):
            logger.info(f"Found LibreOffice at: {cmd}")
            return cmd
    
    logger.error("LibreOffice not found. Please install LibreOffice first.")
    logger.error("Download from: https://www.libreoffice.org/download/")
    return None

def get_libreoffice_version(libreoffice_cmd):
    """Get LibreOffice version to determine which method to use."""
    try:
        result = subprocess.run(
            [libreoffice_cmd, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            version_text = result.stdout.strip()
            logger.info(f"LibreOffice version: {version_text}")
            
            # Extract version number
            import re
            version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_text)
            if version_match:
                major = int(version_match.group(1))
                minor = int(version_match.group(2))
                patch = int(version_match.group(3))
                
                # Check if version is 7.4 or higher
                if major > 7 or (major == 7 and minor >= 4):
                    return 'modern'  # Supports JSON filter options
                elif major >= 6 and minor >= 4:
                    return 'intermediate'  # Supports basic SinglePageSheets
                else:
                    return 'legacy'  # Needs macro approach
            
        return 'unknown'
        
    except Exception as e:
        logger.warning(f"Could not determine LibreOffice version: {e}")
        return 'unknown'

def create_fit_to_page_macro():
    """Create a macro file for older LibreOffice versions."""
    macro_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">
<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">
REM  *****  BASIC  *****

Sub FitToPage
    Dim document As Object, pageStyles As Object
    document = ThisComponent
    pageStyles = document.StyleFamilies.getByName("PageStyles")
    
    For i = 0 To document.Sheets.Count - 1
        Dim sheet As Object, style As Object
        sheet = document.Sheets(i)
        style = pageStyles.getByName(sheet.PageStyle)
        
        ' Set scaling to fit on one page
        style.ScaleToPagesX = 1
        style.ScaleToPagesY = 1
        
        ' Set minimal margins
        style.LeftMargin = 500    ' 5mm
        style.RightMargin = 500   ' 5mm
        style.TopMargin = 500     ' 5mm
        style.BottomMargin = 500  ' 5mm
    Next
    
    On Error Resume Next
    document.storeSelf(Array())
    document.close(true)
End Sub

Sub Main
End Sub

</script:module>'''
    
    return macro_content

def convert_modern_libreoffice(excel_path, output_dir, libreoffice_cmd):
    """Convert using LibreOffice 7.4+ with JSON filter options."""
    try:
        logger.info(f"Converting with modern LibreOffice: {os.path.basename(excel_path)}")
        
        # Use JSON filter options for LibreOffice 7.4+
        filter_options = {
            "SinglePageSheets": {
                "type": "boolean",
                "value": "true"
            }
        }
        
        filter_str = f"pdf:calc_pdf_Export:{json.dumps(filter_options)}"
        
        cmd = [
            libreoffice_cmd,
            '--headless',
            '--convert-to', filter_str,
            '--outdir', output_dir,
            excel_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            base_name = os.path.splitext(os.path.basename(excel_path))[0]
            pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
            
            if os.path.exists(pdf_path):
                logger.info(f"Successfully converted: {os.path.basename(pdf_path)}")
                return True
            else:
                logger.error(f"PDF not created for: {os.path.basename(excel_path)}")
                return False
        else:
            logger.error(f"Modern LibreOffice conversion failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error with modern LibreOffice conversion: {e}")
        return False

def convert_intermediate_libreoffice(excel_path, output_dir, libreoffice_cmd):
    """Convert using LibreOffice 6.4+ with basic SinglePageSheets option."""
    try:
        logger.info(f"Converting with intermediate LibreOffice: {os.path.basename(excel_path)}")
        
        # Try with basic SinglePageSheets option
        cmd = [
            libreoffice_cmd,
            '--headless',
            '--convert-to', 'pdf:calc_pdf_Export:SinglePageSheets=true',
            '--outdir', output_dir,
            excel_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            base_name = os.path.splitext(os.path.basename(excel_path))[0]
            pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
            
            if os.path.exists(pdf_path):
                logger.info(f"Successfully converted: {os.path.basename(pdf_path)}")
                return True
            else:
                logger.error(f"PDF not created for: {os.path.basename(excel_path)}")
                return False
        else:
            logger.error(f"Intermediate LibreOffice conversion failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error with intermediate LibreOffice conversion: {e}")
        return False

def convert_legacy_libreoffice(excel_path, output_dir, libreoffice_cmd):
    """Convert using older LibreOffice versions with macro approach."""
    try:
        logger.info(f"Converting with legacy LibreOffice (using macro): {os.path.basename(excel_path)}")
        
        # Create a temporary macro file
        macro_content = create_fit_to_page_macro()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xba', delete=False) as macro_file:
            macro_file.write(macro_content)
            macro_path = macro_file.name
        
        try:
            # Step 1: Apply macro to set page scaling
            macro_cmd = [
                libreoffice_cmd,
                '--headless',
                '--nologo',
                '--nofirststartwizard',
                '--norestore',
                excel_path,
                f'macro:///{macro_path}///Standard.Module1.FitToPage'
            ]
            
            result = subprocess.run(
                macro_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Step 2: Convert to PDF
            convert_cmd = [
                libreoffice_cmd,
                '--headless',
                '--convert-to', 'pdf:calc_pdf_Export',
                '--outdir', output_dir,
                excel_path
            ]
            
            result = subprocess.run(
                convert_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                base_name = os.path.splitext(os.path.basename(excel_path))[0]
                pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
                
                if os.path.exists(pdf_path):
                    logger.info(f"Successfully converted: {os.path.basename(pdf_path)}")
                    return True
                else:
                    logger.error(f"PDF not created for: {os.path.basename(excel_path)}")
                    return False
            else:
                logger.error(f"Legacy LibreOffice conversion failed: {result.stderr}")
                return False
                
        finally:
            # Clean up macro file
            try:
                os.unlink(macro_path)
            except:
                pass
            
    except Exception as e:
        logger.error(f"Error with legacy LibreOffice conversion: {e}")
        return False

def convert_excel_to_pdf(excel_path, output_dir, libreoffice_cmd, version_type):
    """Convert Excel file to PDF using the appropriate method based on LibreOffice version."""
    
    # Try methods in order of preference
    methods = []
    
    if version_type == 'modern':
        methods = [
            convert_modern_libreoffice,
            convert_intermediate_libreoffice,
            convert_legacy_libreoffice
        ]
    elif version_type == 'intermediate':
        methods = [
            convert_intermediate_libreoffice,
            convert_legacy_libreoffice
        ]
    else:
        methods = [
            convert_legacy_libreoffice,
            convert_intermediate_libreoffice
        ]
    
    for method in methods:
        try:
            if method(excel_path, output_dir, libreoffice_cmd):
                return True
        except Exception as e:
            logger.warning(f"Method {method.__name__} failed: {e}")
            continue
    
    return False

def process_folder(folder_path, libreoffice_cmd, version_type):
    """Process all Excel files in a folder."""
    processed_files = []
    skipped_files = []
    error_files = []
    
    try:
        # Get all files in the folder
        all_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        
        # Filter Excel files
        excel_files = [f for f in all_files if any(f.lower().endswith(ext) for ext in EXCEL_EXTENSIONS)]
        
        if not excel_files:
            logger.debug(f"No Excel files found in {folder_path}")
            return processed_files, skipped_files, error_files
        
        logger.info(f"Found {len(excel_files)} Excel files in {os.path.basename(folder_path)}")
        
        # Process each Excel file
        for excel_file in sorted(excel_files, key=natural_sort_key):
            excel_path = os.path.join(folder_path, excel_file)
            logger.info(f"Processing: {excel_file}")
            
            # Generate PDF filename
            base_name = os.path.splitext(excel_file)[0]
            pdf_filename = f"{base_name}.pdf"
            pdf_path = os.path.join(folder_path, pdf_filename)
            
            # Check if PDF already exists
            if os.path.exists(pdf_path):
                logger.info(f"PDF already exists, skipping: {pdf_filename}")
                skipped_files.append(excel_file)
                continue
            
            # Convert to PDF
            try:
                if convert_excel_to_pdf(excel_path, folder_path, libreoffice_cmd, version_type):
                    processed_files.append(excel_file)
                else:
                    error_files.append(excel_file)
            except Exception as e:
                logger.error(f"Error converting {excel_file}: {e}")
                error_files.append(excel_file)
    
    except Exception as e:
        logger.error(f"Error processing folder {folder_path}: {e}")
    
    return processed_files, skipped_files, error_files

def main():
    """Main function to process all subfolders in the current directory."""
    try:
        # Check if LibreOffice is available
        libreoffice_cmd = check_libreoffice()
        if not libreoffice_cmd:
            logger.error("LibreOffice is required but not found. Please install LibreOffice.")
            logger.error("Installation instructions:")
            logger.error("  macOS: Download from https://www.libreoffice.org/download/")
            logger.error("  Ubuntu/Debian: sudo apt install libreoffice")
            logger.error("  CentOS/RHEL: sudo yum install libreoffice")
            sys.exit(1)
        
        # Determine LibreOffice version and capabilities
        version_type = get_libreoffice_version(libreoffice_cmd)
        
        if version_type == 'modern':
            logger.info("Using modern LibreOffice (7.4+) with JSON filter options")
        elif version_type == 'intermediate':
            logger.info("Using intermediate LibreOffice (6.4+) with basic SinglePageSheets")
        else:
            logger.info("Using legacy LibreOffice with macro approach")
        
        # Get current working directory (mother folder)
        mother_folder = os.getcwd()
        logger.info(f"Processing mother folder: {mother_folder}")
        logger.info("Converting all Excel files in subfolders")
        
        # Find all subfolders
        subfolders = [
            d for d in os.listdir(mother_folder) 
            if os.path.isdir(os.path.join(mother_folder, d))
        ]
        
        if not subfolders:
            logger.info("No subfolders found in the current directory.")
            return
        
        # Sort subfolders
        subfolders.sort(key=natural_sort_key)
        
        logger.info(f"Found {len(subfolders)} subfolders to process")
        
        # Process each subfolder
        total_processed = 0
        total_skipped = 0
        total_errors = 0
        
        for idx, folder in enumerate(subfolders, 1):
            folder_path = os.path.join(mother_folder, folder)
            
            logger.info(f"Processing folder {idx}/{len(subfolders)}: {folder}")
            
            processed, skipped, errors = process_folder(folder_path, libreoffice_cmd, version_type)
            
            total_processed += len(processed)
            total_skipped += len(skipped)
            total_errors += len(errors)
            
            # Log results for this folder
            if processed:
                logger.info(f"  Converted {len(processed)} files: {', '.join(processed)}")
            if skipped:
                logger.debug(f"  Skipped {len(skipped)} files: {', '.join(skipped)}")
            if errors:
                logger.warning(f"  Errors with {len(errors)} files: {', '.join(errors)}")
        
        # Final summary
        logger.info("=" * 60)
        logger.info("CONVERSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total files processed: {total_processed}")
        logger.info(f"Total files skipped: {total_skipped}")
        logger.info(f"Total files with errors: {total_errors}")
        logger.info("Conversion complete!")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("Excel to PDF Converter (Fixed Page Splitting)")
    print("=" * 60)
    print(f"Excel extensions: {', '.join(EXCEL_EXTENSIONS)}")
    print(f"Working directory: {os.getcwd()}")
    print("=" * 60)
    
    main()