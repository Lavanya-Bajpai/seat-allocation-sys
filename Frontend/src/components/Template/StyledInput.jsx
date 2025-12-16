// Frontend/src/components/StyledInput.jsx

import React from 'react';
import styled from 'styled-components';

// Define the styled component for both <input> and <textarea>
const StyledInput = styled.input`
  /* Base styles: Full width, padding, border */
  width: 100%;
  padding: 0.75rem 1rem; /* px-4 py-3 */
  border: 1px solid var(--input-border-color);
  border-radius: 0.5rem; /* rounded-lg */
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); /* shadow-sm */
  transition: all 0.2s ease-in-out;
  
  /* Background and Text colors for light/dark mode */
  background-color: var(--input-bg-color);
  color: var(--input-text-color);
  &::placeholder {
    color: var(--input-placeholder-color);
  }

  /* Focus state */
  &:focus {
    outline: none;
    border-color: var(--input-focus-ring-color);
    box-shadow: 0 0 0 2px var(--input-focus-ring-color-light); /* focus:ring-2 */
  }

  /* Target textarea elements specifically */
  &.textarea {
    resize: vertical;
    min-height: 80px; 
    line-height: 1.5;
  }
`;

// Define the variables based on the theme (needs to be injected via global CSS/context)
// For simplicity in this component, we'll use props or rely on the dark class
// Let's use a function component wrapper to handle the 'as' prop for <textarea>

const InputComponent = ({ type = 'text', rows, className, ...props }) => {
    // If type is 'textarea', render it as a StyledInput with the 'as' prop
    // The className "textarea" helps apply textarea-specific styles in StyledInput
    if (type === 'textarea') {
        return (
            <StyledInput 
                as="textarea" 
                rows={rows} 
                className={`textarea ${className || ''}`}
                {...props} 
            />
        );
    }

    // Default to a standard input field
    return (
        <StyledInput 
            type={type} 
            className={className} 
            {...props} 
        />
    );
};

export default InputComponent;