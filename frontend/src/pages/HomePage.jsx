// frontend/src/pages/HomePage.jsx

import React from 'react';
import SearchPage from './SearchPage';

const HomePage = () => {
  return (
    <SearchPage
      heading="Search Works of Sri Aurobindo and The Mother"
      defaultSearchType="all"
      showSearchTypeControls={true}
    />
  );
};

export default HomePage;
