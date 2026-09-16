import os
import sys
import argparse
import re
from PyPDF2 import PdfMerger, PdfReader
from PIL import Image, ExifTags
import logging
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('pdf_merger')

def natural_sort_key(s):
    """
    Sort strings with embedded numbers in natural order.
    This ensures "2.pdf" comes before "10.pdf"
    """
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', str(s))]

def validate_paths(input_path, output_path):
    """Validate input and output paths."""
    if not os.path.exists(input_path):
        raise ValueError(f"Input path does not exist: {input_path}")
    
    if not os.path.isdir(input_path):
        raise ValueError(f"Input path must be a directory: {input_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)
    
    return os.path.abspath(input_path), os.path.abspath(output_path)

def is_valid_pdf(pdf_path):
    """Check if a PDF file is valid and readable."""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            if len(reader.pages) > 0:
                return True
            else:
                logger.warning(f"PDF has no pages: {pdf_path}")
                return False
    except Exception as e:
        logger.warning(f"Invalid PDF {pdf_path}: {e}")
        return False

def apply_exif_orientation(image):
    """
    Apply EXIF orientation to the image to ensure it's correctly oriented.
    Returns the correctly oriented image.
    """
    try:
        # Check if the image has EXIF data
        if hasattr(image, '_getexif') and image._getexif() is not None:
            exif = {
                ExifTags.TAGS[k]: v
                for k, v in image._getexif().items()
                if k in ExifTags.TAGS
            }
            
            # Apply orientation
            if 'Orientation' in exif:
                orientation = exif['Orientation']
                logger.debug(f"EXIF Orientation: {orientation}")
                
                if orientation == 2:
                    # Horizontal flip
                    return image.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 3:
                    # 180 rotate
                    return image.transpose(Image.ROTATE_180)
                elif orientation == 4:
                    # Vertical flip
                    return image.transpose(Image.FLIP_TOP_BOTTOM)
                elif orientation == 5:
                    # Horizontal flip + 90 rotate right
                    return image.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90)
                elif orientation == 6:
                    # 90 rotate right
                    return image.transpose(Image.ROTATE_270)
                elif orientation == 7:
                    # Horizontal flip + 90 rotate left
                    return image.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
                elif orientation == 8:
                    # 90 rotate left
                    return image.transpose(Image.ROTATE_90)
    except Exception as e:
        logger.warning(f"Error applying EXIF orientation: {e}")
    
    # If no orientation needed or error occurred, return original image
    return image

def image_to_pdf(image_path):
    """
    Convert an image file to PDF while preserving its orientation.
    Returns the PDF's filepath.
    """
    pdf_path = f"{os.path.splitext(image_path)[0]}.temp.pdf"
    try:
        with Image.open(image_path) as img:
            # Preserve original orientation by applying EXIF data
            oriented_img = apply_exif_orientation(img)
            
            # Convert to RGB (needed for some image formats like PNG with transparency)
            img_rgb = oriented_img.convert('RGB')
            
            # Save as PDF
            img_rgb.save(pdf_path)
            
        return pdf_path
    except Exception as e:
        logger.error(f"Error converting image {image_path}: {e}")
        return None

def concat_folder(folder_path):
    """
    Concatenate all PDFs and images in a directory into a single PDF.
    Returns the merger object, temp files, processed files, and errors.
    """
    merger = PdfMerger()
    temp_pdfs = []
    processed_files = []
    skipped_files = []
    error_messages = []

    # Get all files
    try:
        all_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        
        # Sort files in natural order (so 2.pdf comes before 10.pdf)
        all_files.sort(key=natural_sort_key)
        
        logger.info(f"Found {len(all_files)} files in {folder_path}")
        
        for file in all_files:
            filepath = os.path.join(folder_path, file)
            ext = os.path.splitext(file)[1].lower()
            
            # Process PDF files
            if ext == ".pdf":
                logger.info(f"Processing PDF: {file}")
                
                if not os.access(filepath, os.R_OK):
                    error_msg = f"No read permission for file: {filepath}"
                    error_messages.append(error_msg)
                    skipped_files.append(file)
                    logger.error(error_msg)
                    continue
                
                if not is_valid_pdf(filepath):
                    error_msg = f"Invalid or corrupted PDF: {filepath}"
                    error_messages.append(error_msg)
                    skipped_files.append(file)
                    logger.error(error_msg)
                    continue
                
                try:
                    merger.append(filepath)
                    processed_files.append(file)
                    logger.info(f"Successfully appended PDF: {file}")
                except Exception as e:
                    error_msg = f"Error appending PDF {file}: {str(e)}"
                    error_messages.append(error_msg)
                    skipped_files.append(file)
                    logger.error(error_msg)
            
            # Process image files
            elif ext in [".jpg", ".jpeg", ".png", ".tiff", ".bmp", ".gif"]:
                logger.info(f"Processing image: {file}")
                
                try:
                    pdf_file = image_to_pdf(filepath)
                    if pdf_file:
                        temp_pdfs.append(pdf_file)
                        merger.append(pdf_file)
                        processed_files.append(file)
                        logger.info(f"Successfully converted and appended image: {file}")
                    else:
                        error_msg = f"Failed to convert image to PDF: {file}"
                        error_messages.append(error_msg)
                        skipped_files.append(file)
                        logger.error(error_msg)
                except Exception as e:
                    error_msg = f"Error processing image {file}: {str(e)}"
                    error_messages.append(error_msg)
                    skipped_files.append(file)
                    logger.error(error_msg)
            else:
                logger.info(f"Skipping unsupported file type: {file}")
                skipped_files.append(file)
    
    except Exception as e:
        error_msg = f"Error accessing folder {folder_path}: {str(e)}"
        error_messages.append(error_msg)
        logger.error(error_msg)

    return merger, temp_pdfs, processed_files, skipped_files, error_messages

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Merge PDFs and Images in Subfolders')
    parser.add_argument('input_path', help='Path to the mother folder containing subfolders')
    parser.add_argument('output_path', help='Path to the output folder for merged PDFs')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Validate paths
        input_path, output_path = validate_paths(args.input_path, args.output_path)
        
        # Find all subfolders
        subfolders = [
            d for d in os.listdir(input_path) 
            if os.path.isdir(os.path.join(input_path, d))
        ]
        
        # Sort subfolders in natural order
        subfolders.sort(key=natural_sort_key)
        
        logger.info(f"Found {len(subfolders)} subfolders to process")
        
        # Process each subfolder
        for folder in subfolders:
            folder_path = os.path.join(input_path, folder)
            
            logger.info(f"Processing folder: {folder}")
            
            # Generate output PDF name using the subfolder name
            out_pdf_name = f"{folder}.pdf"  # CHANGED: Use subfolder name directly
            out_pdf_path = os.path.join(output_path, out_pdf_name)
            
            # Merge PDFs and images
            merger, temp_pdfs, processed_files, skipped_files, errors = concat_folder(folder_path)
            
            # Write merged PDF
            try:
                if processed_files:  # Only create PDF if files were processed
                    merger.write(out_pdf_path)
                    logger.info(f"Created: {out_pdf_path}")
                    logger.info(f"  Merged {len(processed_files)} files")
                    
                    if args.verbose:
                        for file in processed_files:
                            logger.debug(f"  - {file}")
                else:
                    logger.warning(f"No files to merge in {folder}")
                
                # Log skipped files
                if skipped_files:
                    logger.warning(f"Skipped {len(skipped_files)} files in {folder}")
                    if args.verbose:
                        for file in skipped_files:
                            logger.debug(f"  - {file}")
                
                # Log errors
                if errors:
                    logger.warning(f"Encountered {len(errors)} errors in {folder}")
                    if args.verbose:
                        for error in errors:
                            logger.debug(f"  - {error}")
                            
            except Exception as e:
                logger.error(f"Error creating PDF for {folder}: {e}")
                logger.error(traceback.format_exc())
            finally:
                # Close merger and remove temporary files
                merger.close()
                for temp_pdf in temp_pdfs:
                    try:
                        os.remove(temp_pdf)
                    except Exception as e:
                        logger.warning(f"Failed to remove temp file {temp_pdf}: {e}")
        
        logger.info("Processing complete!")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()