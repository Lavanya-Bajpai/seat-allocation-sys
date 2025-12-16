// Frontend/src/components/PatternBackground.jsx
import React from 'react';
import styled, { keyframes } from 'styled-components';

// Define the keyframes for the animation
const move = keyframes`
  0% {
    background-position: 0 0;
  }
  100% {
    background-position: 40px 40px;
  }
`;

const StyledContainer = styled.div`
  /* Set the container to cover the entire viewport */
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: -1; /* Ensure it stays behind all content */
  overflow: hidden;

  /* Wallpaper styling based on your example */
  background: ${props => props.$isDark ? '#121212' : '#f0f0f0'}; 
  background-image: linear-gradient(
    135deg,
    ${props => props.$isDark ? '#121212' : '#ffffff'} 25%,
    ${props => props.$isDark ? '#1a1a1a' : '#f5f5f5'} 25%,
    ${props => props.$isDark ? '#1a1a1a' : '#f5f5f5'} 50%,
    ${props => props.$isDark ? '#121212' : '#ffffff'} 50%,
    ${props => props.$isDark ? '#121212' : '#ffffff'} 75%,
    ${props => props.$isDark ? '#1a1a1a' : '#f5f5f5'} 75%,
    ${props => props.$isDark ? '#1a1a1a' : '#f5f5f5'}
  );
  background-size: 40px 40px;

  animation: ${move} 4s linear infinite;
`;

const PatternBackground = ({ isDark }) => {
  return (
    // Pass isDark as a transient prop ($isDark) to styled-components
    <StyledContainer $isDark={isDark} />
  );
}

export default PatternBackground;