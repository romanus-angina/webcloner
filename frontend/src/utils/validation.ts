import { isValidUrl } from './helpers';

export interface ValidationResult {
  isValid: boolean;
  error?: string;
}

export function validateUrl(url: string): ValidationResult {
  if (!url.trim()) {
    return { isValid: false, error: "URL is required" };
  }

  if (!isValidUrl(url)) {
    return { isValid: false, error: "Please enter a valid URL" };
  }

  // Check for localhost/internal URLs (security)
  const urlObj = new URL(url);
  const hostname = urlObj.hostname.toLowerCase();
  
  const forbiddenHosts = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '::1'
  ];

  if (forbiddenHosts.includes(hostname) || 
      hostname.match(/^192\.168\./) ||
      hostname.match(/^10\./) ||
      hostname.match(/^172\.(1[6-9]|2[0-9]|3[0-1])\./)) {
    return { isValid: false, error: "Local URLs are not allowed for security reasons" };
  }

  return { isValid: true };
}

export function validateEmail(email: string): ValidationResult {
  if (!email.trim()) {
    return { isValid: false, error: "Email is required" };
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return { isValid: false, error: "Please enter a valid email address" };
  }

  return { isValid: true };
}

export function validateRequired(value: string, fieldName: string): ValidationResult {
  if (!value.trim()) {
    return { isValid: false, error: `${fieldName} is required` };
  }

  return { isValid: true };
}

export function validateLength(
  value: string, 
  minLength: number, 
  maxLength: number, 
  fieldName: string
): ValidationResult {
  if (value.length < minLength) {
    return { 
      isValid: false, 
      error: `${fieldName} must be at least ${minLength} characters` 
    };
  }

  if (value.length > maxLength) {
    return { 
      isValid: false, 
      error: `${fieldName} must be no more than ${maxLength} characters` 
    };
  }

  return { isValid: true };
}