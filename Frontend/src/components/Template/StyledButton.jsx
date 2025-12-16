// Frontend/src/components/StyledButton.jsx
import React from 'react';
import styled from 'styled-components';

const StyledWrapper = styled.button`
  /* Your complex button CSS logic using styled-components */
  position: relative;
  font-family: inherit;
  font-weight: 500;
  font-size: 16px; /* Adjusted size slightly for better fit */
  letter-spacing: 0.05em;
  border-radius: 0.3em;
  cursor: pointer;
  border: none;
  overflow: hidden;
  transition: transform 0.2s;
  
  /* Apply dynamic color based on props */
  background: ${props => {
    switch (props.$variant) {
      case 'save':
        return 'linear-gradient(to right, #4CAF50, #2E7D32)'; // Green for Save
      case 'download':
        return 'linear-gradient(to right, #2196F3, #1565C0)'; // Blue for Download
      case 'reload':
        return 'linear-gradient(to right, #FFC107, #FF8F00)'; // Amber for Reload
      default:
        return 'linear-gradient(to right, #8e2de2, #4a00e0)'; // Default Purple
    }
  }};
  
  color: ghostwhite;
  
  /* Disabled state */
  &:disabled {
    cursor: not-allowed;
    background: #616161;
    color: #bdbdbd;
    transform: none;
  }

  .button-content {
    position: relative;
    z-index: 10;
    transition: color 0.4s;
    display: inline-flex;
    align-items: center;
    padding: 0.8em 1.2em 0.8em 1.05em;
  }

  svg {
    width: 1.2em;
    height: 1.2em;
    margin-right: 0.5em;
    vertical-align: middle;
  }

  &::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 0;
    background: #00000030; /* Dark overlay for hover effect */
    width: 120%;
    left: -10%;
    transform: skew(30deg);
    transition: transform 0.4s cubic-bezier(0.3, 1, 0.8, 1);
  }

  &:not(:disabled):hover::before {
    transform: translate3d(100%, 0, 0);
  }

  &:not(:disabled):active {
    transform: scale(0.95);
  }
`;

const StyledButton = ({ onClick, children, disabled, type = 'button', variant = 'default', className = '' }) => {
    return (
        <StyledWrapper
            type={type}
            onClick={onClick}
            disabled={disabled}
            $variant={variant} // Use transient prop
            className={className}
        >
            <span className="button-content">
                {children}
            </span>
        </StyledWrapper>
    );
};

export default StyledButton;