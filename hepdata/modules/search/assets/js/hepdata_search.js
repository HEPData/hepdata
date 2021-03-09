import $ from 'jquery'
import HEPDATA from './hepdata_common.js'

HEPDATA.search = {
  show_more_datatables: function(publication, show_number) {
    var tables = $("#publication-" + publication
            + " .data-brief:not(:visible)");

    tables.slice(0, show_number).removeClass("hidden");

    if (tables.length <= show_number) {
        $("#publication-" + publication + " .data-more").hide();
    }
  }
}
