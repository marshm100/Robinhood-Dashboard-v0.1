/**
 * Utility functions for date handling in Robinhood Dashboard
 */

/**
 * Format a date string from MM/DD/YYYY to YYYY-MM-DD for storage in the database
 * @param {string} dateStr - Date string in MM/DD/YYYY format (e.g., "3/10/2025")
 * @returns {string} Formatted date in YYYY-MM-DD format
 */
function formatDateForDatabase(dateStr) {
  // Step 1: Check if the input string is valid and not empty.
  if (!dateStr || dateStr.trim() === '') {
    // Step 2: If the string is empty or invalid, return an empty string.
    return '';
  }
  
  try {
    // Step 3: Split the date string by the '/' character.
    const parts = dateStr.split('/');
    // Step 4: Check if the split results in exactly 3 parts (month, day, year).
    if (parts.length !== 3) {
      // Step 5: If not 3 parts, return the original string as it's not in the expected format.
      return dateStr;
    }
    
    // Step 6: Get the month part and ensure it's 2 digits (e.g., '03').
    const month = parts[0].padStart(2, '0');
    // Step 7: Get the day part and ensure it's 2 digits (e.g., '10').
    const day = parts[1].padStart(2, '0');
    // Step 8: Get the year part.
    const year = parts[2];
    
    // Step 9: Combine the parts into YYYY-MM-DD format.
    return `${year}-${month}-${day}`;
  } catch (error) {
    // Step 10: If any error occurs during the process, log the error.
    console.error('Error formatting date:', error);
    // Step 11: Return the original date string as a fallback.
    return dateStr;
  }
}

/**
 * Format a date to YYYYMMDD format
 * @param {string|Date} date - Date object or string in YYYY-MM-DD format
 * @returns {string} Date in YYYYMMDD format
 */
function toYYYYMMDD(date) {
  try {
    // Step 1: Declare a variable to hold the Date object.
    let dateObj;
    
    // Step 2: Check if the input 'date' is a string.
    if (typeof date === 'string') {
      // Step 3: Check if the string is already in YYYY-MM-DD format.
      if (date.match(/^\d{4}-\d{2}-\d{2}$/)) {
        // Step 4: If it is, remove the hyphens and return.
        return date.replace(/-/g, '');
      }
      
      // Step 5: If not in YYYY-MM-DD, try to create a Date object from the string.
      dateObj = new Date(date);
    // Step 6: Check if the input 'date' is already a Date object.
    } else if (date instanceof Date) {
      // Step 7: If it is, assign it to dateObj.
      dateObj = date;
    } else {
      // Step 8: If it's neither a string nor a Date object, return an empty string.
      return '';
    }
    
    // Step 9: Check if the created Date object is valid.
    if (isNaN(dateObj.getTime())) {
      // Step 10: If invalid, return an empty string.
      return '';
    }
    
    // Step 11: Get the full year from the Date object.
    const year = dateObj.getFullYear();
    // Step 12: Get the month (0-11), add 1, convert to string, and pad with '0' if needed.
    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
    // Step 13: Get the day of the month, convert to string, and pad with '0' if needed.
    const day = String(dateObj.getDate()).padStart(2, '0');
    
    // Step 14: Combine year, month, and day into YYYYMMDD format.
    return `${year}${month}${day}`;
  } catch (error) {
    // Step 15: If any error occurs, log the error.
    console.error('Error formatting date to YYYYMMDD:', error);
    // Step 16: Return an empty string as a fallback.
    return '';
  }
}

/**
 * Get a date range for a given period (e.g., '1m', '3m', '1y', etc.)
 * @param {string} period - Time period code
 * @returns {Object} Object with startDate and endDate (Date objects)
 */
function getDateRange(period) {
  // Step 1: Get the current date as the end date.
  const endDate = new Date();
  // Step 2: Create a copy of the end date to use as the start date.
  const startDate = new Date();
  
  // Step 3: Adjust the start date based on the requested period.
  switch (period) {
    case '1m': // 1 month ago
      startDate.setMonth(endDate.getMonth() - 1);
      break;
    case '3m': // 3 months ago
      startDate.setMonth(endDate.getMonth() - 3);
      break;
    case '6m': // 6 months ago
      startDate.setMonth(endDate.getMonth() - 6);
      break;
    case '1y': // 1 year ago
      startDate.setFullYear(endDate.getFullYear() - 1);
      break;
    case '3y': // 3 years ago
      startDate.setFullYear(endDate.getFullYear() - 3);
      break;
    case '5y': // 5 years ago
      startDate.setFullYear(endDate.getFullYear() - 5);
      break;
    case '10y': // 10 years ago
      startDate.setFullYear(endDate.getFullYear() - 10);
      break;
    default:
      // Step 4: If the period is unknown, default to 1 year ago.
      startDate.setFullYear(endDate.getFullYear() - 1);
  }
  
  // Step 5: Return an object containing the calculated start and end dates.
  return { startDate, endDate };
}

/**
 * Parse a date string to a Date object, supporting various formats
 * @param {string} dateStr - Date string
 * @returns {Date|null} Date object or null if invalid
 */
function parseDate(dateStr) {
  // Step 1: Check if the input date string is provided.
  if (!dateStr) return null; // Return null if no string is given.
  
  try {
    // Step 2: Try creating a Date object directly from the string (handles ISO format like YYYY-MM-DD).
    const date = new Date(dateStr);
    // Step 3: Check if the created Date object is valid.
    if (!isNaN(date.getTime())) {
      // Step 4: If valid, return the Date object.
      return date;
    }
    
    // Step 5: If direct parsing failed, check if the string contains '/'.
    if (dateStr.includes('/')) {
      // Step 6: Split the string by '/' assuming MM/DD/YYYY format.
      const parts = dateStr.split('/');
      // Step 7: Check if there are exactly 3 parts.
      if (parts.length === 3) {
        // Step 8: Parse month, day, and year from the parts.
        // Note: JavaScript months are 0-indexed (0 = January, 11 = December).
        const month = parseInt(parts[0], 10) - 1;
        const day = parseInt(parts[1], 10);
        const year = parseInt(parts[2], 10);
        // Step 9: Create a new Date object using year, month, day.
        const dateFromParts = new Date(year, month, day);
        // Step 10: Check if this Date object is valid.
        if (!isNaN(dateFromParts.getTime())) {
          // Step 11: If valid, return the Date object.
          return dateFromParts;
        }
      }
    }
    
    // Step 12: If all parsing attempts fail, return null.
    return null;
  } catch (error) {
    // Step 13: If any error occurs during parsing, log the error.
    console.error('Error parsing date:', error);
    // Step 14: Return null as a fallback.
    return null;
  }
}

// Step 15: Export the utility functions to be used in other files.
module.exports = {
  formatDateForDatabase,
  toYYYYMMDD,
  getDateRange,
  parseDate
};