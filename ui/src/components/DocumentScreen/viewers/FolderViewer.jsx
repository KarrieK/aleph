import React, { Component } from 'react';
import { withRouter } from 'react-router';
import SearchContext from 'src/components/SearchScreen/SearchContext';

import './FolderViewer.css';

class FolderViewer extends Component {
  render() {
    const { document } = this.props;

    if (!document || !document.id || !document.links) {
      return null;
    }
    const context = {
      'filter:parent.id': document.id
    };
    const aspects = {
      filter: false,
      countries: false,
      collections: false
    };
    return (
      <div id="children" className="FolderViewer">
        <SearchContext collection={document.collection}
                       context={context}
                       aspects={aspects} />
      </div>
    );
  }
}

FolderViewer = withRouter(FolderViewer)
export default FolderViewer;
