
import os
import glob
import re
import sys
import uuid
import logging

# ==============================================================================
# CONFIGURATION - Change these constants to customize the naming pattern
# ==============================================================================

PREFIX = "富泰和德国-穿行测试"    # inputname1 - Change this to your desired prefix
SUFFIX = "-博世汽车部件（苏州）有限公司南京分公司-"        # inputname2 - Change this to your desired suffix

# NOTE: The SUFFIX above contains "2024年" which is hardcoded. The extracted year 
# will be appended at the end. If you don't want duplicate years, consider removing 
# the year from the SUFFIX and let only the extracted year be used.

# ==============================================================================
# Script Implementation
# ==============================================================================

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('pdf_renamer')

def natural_sort_key(s):
    """
    Sort strings with embedded numbers in natural order.
    This ensures "file1.pdf" comes before "file10.pdf"
    """
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', str(s))]

def extract_year_and_count(filename):
    """
    Extract year and counting number from filename.
    
    Expected pattern: companyname/location + year + "-" + counting_number + "-" + other_stuff
    
    Args:
        filename: The PDF filename (without extension)
        
    Returns:
        tuple: (year, counting_number) or (None, None) if extraction fails
    """
    # Split by hyphens to get the parts
    parts = filename.split('-')
    
    if len(parts) < 2:
        return None, None
    
    # Extract year from the first part (before first hyphen)
    first_part = parts[0]
    year_match = re.search(r'(202[0-5])', first_part)
    
    if not year_match:
        return None, None
    
    year = year_match.group(1)
    
    # Extract counting number (between first and second hyphen)
    counting_number = parts[1]
    
    return year, counting_number

def main():
    try:
        # Get current working directory
        current_dir = os.getcwd()
        logger.info(f"Working in directory: {current_dir}")
        
        # Find all PDF files in current directory
        pdf_files = glob.glob('*.pdf')
        
        if not pdf_files:
            logger.info("No PDF files found in the current directory.")
            return
        
        # Sort files in natural order
        pdf_files.sort(key=natural_sort_key)
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Parse files and extract year/counting number
        valid_old_files = []
        valid_new_names = []
        skip_files = []
        
        for file in pdf_files:
            # Remove .pdf extension to get base filename
            base_name = os.path.splitext(file)[0]
            
            # Extract year and counting number
            year, count_token = extract_year_and_count(base_name)
            
            if year is None or count_token is None:
                skip_files.append(file)
                continue
            
            # Generate new name: PREFIX + counting_number + SUFFIX + YEAR + .pdf
            new_name = f"{PREFIX}{count_token}{SUFFIX}{year}年.pdf"
            
            valid_old_files.append(file)
            valid_new_names.append(new_name)
        
        # Log skipped files
        if skip_files:
            logger.warning(f"Skipped {len(skip_files)} files that didn't match the expected pattern:")
            for i, f in enumerate(skip_files, 1):
                logger.warning(f"  {i:2d}. {f}")
        
        if not valid_old_files:
            logger.info("No valid PDF files found that match the pattern.")
            return
        
        logger.info(f"Found {len(valid_old_files)} valid files to rename")
        
        # Check for duplicate new names
        seen = {}
        duplicates = {}
        for i, new_name in enumerate(valid_new_names):
            if new_name in seen:
                if new_name not in duplicates:
                    duplicates[new_name] = [seen[new_name]]
                duplicates[new_name].append(valid_old_files[i])
            else:
                seen[new_name] = valid_old_files[i]
        
        if duplicates:
            logger.error("Duplicate new names detected. The following files would be renamed to the same new name:")
            for new_name, files in duplicates.items():
                logger.error(f"  New name: {new_name}")
                for f in files:
                    logger.error(f"      Source: {f}")
            logger.error("Please adjust the pattern or manually rename these files to avoid conflicts.")
            return
        
        # Check for conflicts with existing files
        existing_files = set(os.listdir('.'))
        conflicts = []
        for new_name in valid_new_names:
            if new_name in existing_files and new_name not in valid_old_files:
                conflicts.append(new_name)
        
        if conflicts:
            logger.error("The following new names conflict with existing files:")
            for c in conflicts:
                logger.error(f"  - {c}")
            logger.error("Please resolve these conflicts before running the script.")
            return
        
        # Generate temporary names to avoid conflicts during renaming
        temp_names = []
        for i in range(len(valid_old_files)):
            temp_name = f"{str(uuid.uuid4())}.tmp"
            temp_names.append(temp_name)
        
        logger.info("Starting rename process...")
        
        # First pass: rename all files to temporary names
        logger.info("Phase 1: Moving files to temporary names...")
        for old_file, temp_name in zip(valid_old_files, temp_names):
            try:
                os.rename(old_file, temp_name)
                logger.debug(f"Temporarily renamed: {old_file} -> {temp_name}")
            except Exception as e:
                logger.error(f"Error renaming {old_file} to {temp_name}: {e}")
                # Try to revert previous renames
                logger.info("Attempting to revert previous renames...")
                for j in range(valid_old_files.index(old_file)):
                    try:
                        os.rename(temp_names[j], valid_old_files[j])
                    except Exception:
                        pass
                return
        
        # Second pass: rename temporary files to final names
        logger.info("Phase 2: Applying final names...")
        for temp_name, new_name in zip(temp_names, valid_new_names):
            try:
                os.rename(temp_name, new_name)
                logger.info(f"Final rename: {new_name}")
            except Exception as e:
                logger.error(f"Error renaming {temp_name} to {new_name}: {e}")
                # Try to revert to original names
                logger.info("Attempting to revert to original names...")
                for j in range(temp_names.index(temp_name)):
                    try:
                        os.rename(valid_new_names[j], valid_old_files[j])
                    except Exception:
                        pass
                # Revert remaining temp files
                for j in range(temp_names.index(temp_name), len(temp_names)):
                    try:
                        os.rename(temp_names[j], valid_old_files[j])
                    except Exception:
                        pass
                return
        
        logger.info("✅ Rename process completed successfully!")
        logger.info(f"Renamed {len(valid_old_files)} files.")
        
        # Show summary
        logger.info("\nRename Summary:")
        for i, (old_name, new_name) in enumerate(zip(valid_old_files, valid_new_names), 1):
            logger.info(f"  {i:2d}. {old_name} -> {new_name}")
    
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("PDF Rename Script")
    print("=" * 60)
    print(f"Renaming pattern: {PREFIX}[count_token]{SUFFIX}[year].pdf")
    print(f"Working directory: {os.getcwd()}")
    print("=" * 60)
    print("Note: Year (2020-2025) and counting number will be extracted from existing filenames")
    print("Files that don't match the expected pattern will be skipped")
    print("=" * 60)
    
    # Ask for confirmation
    try:
        confirm = input("\nProceed with renaming? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("Operation cancelled.")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)
    
    main()
