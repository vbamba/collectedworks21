// frontend/src/pages/SemanticPage.jsx

import React from 'react';
import SearchPage from './SearchPage';

const SemanticPage = () => {
  return (
    <SearchPage
      heading="Ask a Question"
      defaultSearchType="semantic"
      showSearchTypeControls={false}
    />
  );
};

export default SemanticPage;
