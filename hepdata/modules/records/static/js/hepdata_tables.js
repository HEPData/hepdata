/**
 * Created by eamonnmaguire on 16/03/2016.
 */


HEPDATA.switch_table = function (listId, table_requested, table_name, status) {
  // clear the active class
  $(listId + '>li').each(function () {
    $(this).removeClass("active")
  });
  // now set the active class on the table just selected
  $('#' + table_requested).addClass("active");


  HEPDATA.render_loader("#table_loader", [
      {x: 26, y: 30, color: "#955BA5"},
      {x: -60, y: 55, color: "#2C3E50"},
      {x: 37, y: -10, color: "#955BA5"},
      {x: -60, y: 10, color: "#955BA5"},
      {x: -27, y: -30, color: "#955BA5"},
      {x: 60, y: -55, color: "#2C3E50"}],
    {"width": 200, "height": 200}
  );

  // Pass the table name from record-javascript.html or table_list.html before it gets mangled by MathJax.
  var _name = table_name;
  if (!_name) {
    // Only use jQuery when called from table_details.html where '$' symbols are stripped from table names.
    _name = $('[value="' + table_requested + '"]').text();  //
  }
  if (_name.match(/^Table \d+$/)) {
    _name = _name.replace("Table ", "Table");
  }

  var _recid = HEPDATA.current_inspire_id && status == 'finished' ? 'ins' + HEPDATA.current_inspire_id : HEPDATA.current_record_id;
  var direct_link = HEPDATA.site_url + '/record/' + _recid
    + '?version=' + HEPDATA.current_table_version + "&table=" + _name.replace(/\+/g, '%2B').replace(/ /g, '%20');

  $("#direct_data_link").val(direct_link);
  $(".copy-btn").attr('data-clipboard-text', direct_link);
  if (HEPDATA.clipboard == undefined) {
    HEPDATA.clipboard = new Clipboard('.copy-btn');
    toastr.options.timeOut = 3000;

    HEPDATA.clipboard.on('success', function (e) {
      toastr.success($(".copy-btn").attr('data-clipboard-text') + ' copied to clipboard.')
    });

    HEPDATA.clipboard.on('error', function (e) {
      if (navigator.userAgent.indexOf("Safari") > -1) {
        toastr.success('Press &#8984; + C to finalise copy');
      } else {
        toastr.error('There was a problem copying the link.');
      }
    })
  }


  $("#hepdata_table_loading").removeClass("hidden");
  $("#hepdata_table_loading_failed").addClass("hidden");
  $("#hepdata_table_loader").removeClass("hidden");
  $("#hepdata_table_content").addClass("hidden");

  HEPDATA.current_table_id = table_requested;

  if (HEPDATA.show_review) {
    HEPDATA.load_review_messages("#review_messages",
      HEPDATA.current_record_id,
      HEPDATA.current_table_id);
  }
  HEPDATA.table_renderer.display_table('/record/data/' + HEPDATA.current_record_id + '/' + table_requested + "/" + HEPDATA.current_table_version,
    '#data_table_region',
    '#data_visualization_region');

  $(".data_download_link").each(function () {
    var data_format = $(this).text().toLowerCase();
    var data_url = '/download/table/' + _recid + '/' + _name.replace(/%/g, '%25').replace(/\\/g, '%5C') + '/' + HEPDATA.current_table_version + '/' + data_format;
    $(this).attr('href', data_url);
  });

  $("#json_link").attr('href', '/download/table/' + _recid + '/' + _name.replace(/%/g, '%25').replace(/\\/g, '%5C') + '/' + HEPDATA.current_table_version + '/json')
};

HEPDATA.table_renderer = {
  display_table: function (url, table_placement, visualization_placement) {

    $.ajax({
      dataType: "json",
      url: url,
      processData: false,
      cache: true,
      success: function (table_data) {
        // display the table
        d3.select(table_placement).html('');
        d3.select("#table_options_region").html('');

        HEPDATA.current_table_name = table_data.name;

        $("#table_name").text(table_data.name);
        $("#table_location").html(table_data.location);
        $("#table_doi_contents").html('<a href="https://doi.org/' + table_data.doi + '" target="_blank">' + table_data.doi + '</a>');

        $("#table_description").html((table_data.description.indexOf('.') == 0) ? '' : table_data.description.trim());

        HEPDATA.table_renderer.render_keywords(table_data.keywords, "#table_keywords");

        HEPDATA.reset_stats();

        HEPDATA.table_renderer.render_qualifiers(table_data, table_placement);
        HEPDATA.table_renderer.render_headers(table_data, table_placement);
        HEPDATA.table_renderer.render_data(table_data, table_placement);

        HEPDATA.render_associated_files(table_data.associated_files, '#support-files');

        if (table_data["x_count"] > 1) {
          HEPDATA.visualization.heatmap.reset();
          HEPDATA.visualization.heatmap.render(table_data, visualization_placement, {
            width: 300,
            height: 300
          });
          HEPDATA.table_renderer.attach_row_listener(table_placement, 'heatmap');
        } else if (table_data["values"].length == 0) {
          // No data to display
          d3.select(visualization_placement).html("");
          d3.select("#legend").html("");
          var no_data_info = d3.select(visualization_placement).append("div").style("text-align","center");
          no_data_info.append("img").attr("src", "/static/img/nodata.svg").attr({"width": 100, height: 100});
          no_data_info.append("p").text("No data to display...").style({"font-size": 14, "color": "#aaa"})
        } else if (table_data["x_count"] === 1) {
          HEPDATA.visualization.histogram.render(table_data, visualization_placement, {
            width: 300,
            height: 300,
            "mode": "histogram"
          });
          HEPDATA.table_renderer.attach_row_listener(table_placement, 'histogram');
        }
        MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        HEPDATA.table_renderer.update_reviewer_button(table_data.review);

        $("#hepdata_table_loader").addClass("hidden");
        $("#hepdata_table_content").removeClass("hidden");
      },
      error: function (data, error) {
        console.error(error);
        d3.select("#hepdata_table_loading_failed_text").html('Failed to load table defined by ' + url);
        $("#hepdata_table_loading").addClass("hidden");
        $("#hepdata_table_loading_failed").removeClass("hidden");
      }
    });
  },

  attach_row_listener: function (table_placement, type) {

    $(table_placement + ' tr').mouseover(function (e) {
      var row_id = $(e.target).parents('tr').attr('id');
      if (row_id) {
        var row = row_id.split("-")[1];

        var target = d3.selectAll(".node");
        if (type === "heatmap") {
          target = target.selectAll("rect");
        }
        target
          .transition().style('opacity', function (d) {
          return d.row == row ? 1 : 0.1;
        });

      }
    });

    $(table_placement + ' tr').mouseout(function (e) {
      var target = d3.selectAll(".node");
      if (type === "heatmap") {
        target = target.selectAll("rect");
      }
      target
        .transition().style('opacity', 1);
    });

  },

  update_reviewer_button: function (review_info) {
    HEPDATA.set_review_status(review_info.review_flag);
  },

  clean_data: function (value, remove_qualifier_uniqueness_attr) {

    if (remove_qualifier_uniqueness_attr) value = value.replace(/-\d+/, "");
    if (value == ".") {
      value = ""
    }
    return value;
  },

  render_keywords: function (keywords, placement) {
    $(placement + " .row-fluid").html('');
    for (var keyword_key in keywords) {
      var keyword_items = [];

      for (var value in keywords[keyword_key]) {
        keyword_items.push({'key': keyword_key, 'value': keywords[keyword_key][value]});
      }

      var col_width = parseInt((12 / (Object.keys(keywords).length)));
      var li = d3.select(placement + " .row-fluid").append('div')
        .attr('class', 'keyword-item col-md-' + col_width);

      li.append('h4').text(keyword_key);
      var individual_keyword_value_list = li.append('ul').attr('class', 'keyword_values');

      var individual_kw = individual_keyword_value_list.selectAll("a").data(keyword_items)
        .enter().append('li').attr('class', 'chip');

      var individual_kw_link = individual_kw.append('a').attr('href', function (d) {
        val = d.value.trim().replace(/\+/g, "%2B").replace(/\s/g, "+")
        if (d.key == 'cmenergies') {
          val = val.replace(/-/g, "%2C")
        }
        return '/search?q=&' + d.key + "=" + val;
      });

      individual_kw_link.append('i').attr('class', 'fa fa-tag').style({'margin-right': '5px', 'display': 'inline'});
      individual_kw_link.append('span').text(function (d) {
        return d.value.length > 60 ? d.value.substring(0, 60) + "..." : d.value;
      });
    }
  },

  render_qualifiers: function (table_data, placement) {
    for (var qualifier_idx in table_data["qualifier_order"]) {
      var qualifier_type = table_data["qualifier_order"][qualifier_idx];

      var qualifier_block = d3.select(placement).append('tr').attr('class', 'qualifiers');

      qualifier_block.append('td').attr('class', 'qualifier_name').attr('colspan', table_data["x_count"]).text(HEPDATA.table_renderer.clean_data(qualifier_type, true));

      for (var qualifier_data_idx in table_data.qualifiers[qualifier_type]) {
        qualifier_block.append('td').attr('class', 'qualifier_value').attr('colspan', table_data.qualifiers[qualifier_type][qualifier_data_idx].colspan).text(HEPDATA.table_renderer.clean_data(table_data.qualifiers[qualifier_type][qualifier_data_idx].value));
      }
    }
  },

  render_headers: function (table_data, placement) {
    var header_section = d3.select(placement).append('tr').attr('class', 'headers');

    for (var header_idx in table_data.headers) {
      header_section.append('td').attr('class', 'x').attr('colspan', table_data.headers[header_idx].colspan).text(table_data.headers[header_idx].name);
    }
  },

  render_data: function (table_data, placement) {


    for (var value_idx in table_data.values) {
      var value_obj = table_data.values[value_idx];

      var tr = d3.select(placement).append("tr").attr("class", "data_values").attr("id", "row-" + value_idx);
      if (value_idx > HEPDATA.default_row_limit) tr.classed('hidden', true);

      for (var x_idx in value_obj.x) {
        var td;
        if ('value' in value_obj.x[x_idx] && 'low' in value_obj.x[x_idx] && 'high' in value_obj.x[x_idx]) {
          tr.append("td").text(value_obj.x[x_idx]['value'] + ' (bin: ' +
            value_obj.x[x_idx]['low'] + ' - ' + value_obj.x[x_idx]['high'] + ')');
        } else if ('low' in value_obj.x[x_idx] && 'high' in value_obj.x[x_idx]) {
          td = tr.append('td').text(value_obj.x[x_idx]['low'] + ' - ' + value_obj.x[x_idx]['high']);
        } else {
          td = tr.append("td").text(value_obj.x[x_idx]['value']);
        }
      }

      for (var y_idx in value_obj.y) {
        var value = value_obj.y[y_idx].value;
        td = tr.append('td');
        if (value != undefined) {

          var decimal_places = HEPDATA.count_decimals(value);
          var div = td.append('div');
          div.append('span').text(value);

          var errors = value_obj.y[y_idx].errors;

          for (var error_idx in errors) {

            var err_class = "error " + ((error_idx < HEPDATA.default_errors_to_show) ? "" : "hidden");

            if ("asymerror" in errors[error_idx]) {

              var plus_error = ('plus' in errors[error_idx]['asymerror']) ? errors[error_idx]['asymerror']['plus'] : '';
              var min_error = ('minus' in errors[error_idx]['asymerror']) ? errors[error_idx]['asymerror']['minus'] : '';

              // Round errors to same number of decimal places as central value.
              // Comment out for now: misleading if central value lacks significant trailing zeros.
              // This is the case for the YAML format used for all records migrated from the old HepData site.
              /*
              if (plus_error.toString().toLowerCase().indexOf('e') == -1 && value.toString().toLowerCase().indexOf('e') == -1) {
                var plus_error_rounded = HEPDATA.visualization.utils.round(plus_error, decimal_places);
                if (plus_error_rounded != 0)
                  plus_error = plus_error_rounded;
              }
              if (min_error.toString().toLowerCase().indexOf('e') == -1 && value.toString().toLowerCase().indexOf('e') == -1) {
                var min_error_rounded = HEPDATA.visualization.utils.round(min_error, decimal_places);
                if (min_error_rounded != 0)
                  min_error = min_error_rounded;
              }
              */


              var plus_error_num = HEPDATA.dataprocessing.process_error_value(plus_error, value);
              var min_error_num = HEPDATA.dataprocessing.process_error_value(min_error, value);

              var error = div.append('div').attr('class', err_class);

              var value_block = error.append('div').attr('class', 'value');
              var asym_block = value_block.append('div').attr('class', 'asym');
              asym_block.append('span').attr('class', 'sup').text(
                (plus_error != '' && plus_error[0] != '+' && plus_error[0] != '-' && plus_error_num >= 0 ? '+' : '') +
                plus_error);
              asym_block.append('span').attr('class', 'sub').text(
                (min_error_num > 0 && min_error[0] != '+' && min_error[0] != '-' ? '+' : '') +
                (min_error != '' && min_error_num == 0 && min_error[0] != '+' && min_error[0] != '-' && (plus_error_num == 0 && plus_error[0] == '-') ? '+' : '') +
                (min_error != '' && min_error_num == 0 && min_error[0] != '+' && min_error[0] != '-' && (plus_error_num == 0 && plus_error[0] != '-') ? '-' : '') +
                min_error);
              if (errors[error_idx]["label"] !== undefined)
                value_block.append('div').attr('class', 'label').text(errors[error_idx]["label"] == undefined ? HEPDATA.default_error_label : errors[error_idx]["label"]);

            } else if ("symerror" in errors[error_idx]) {
              if (errors[error_idx]['symerror'] != 0) {
                var sym_error = errors[error_idx]['symerror'];

                // Round errors to same number of decimal places as central value.
                // Comment out for now: misleading if central value lacks significant trailing zeros.
                // This is the case for the YAML format used for all records migrated from the old HepData site.
                /*
                if (sym_error.toString().toLowerCase().indexOf('e') == -1 && value.toString().toLowerCase().indexOf('e') == -1) {
                  var sym_error_rounded = HEPDATA.visualization.utils.round(sym_error, decimal_places);
                  if (sym_error_rounded != 0)
                    sym_error = sym_error_rounded;
                }
                */


                var sym_error_num = HEPDATA.dataprocessing.process_error_value(sym_error, value);

                var error = div.append('div').attr('class', err_class + ' sym');
                error.append('div').attr('class', 'value').html(sym_error_num >= 0 ? '&#177;' + sym_error : '&#8723;' + sym_error.replace('-', ''));

                if (errors[error_idx]["label"] !== undefined)
                  error.append('div').attr('class', 'label').text(errors[error_idx]["label"] == undefined ? HEPDATA.default_error_label : errors[error_idx]["label"]);
              }
            }
          }

          if (errors.length > HEPDATA.default_errors_to_show) {
            var more_errors_to_show = errors.length - HEPDATA.default_errors_to_show;
            div.append('span').text('+ ' + more_errors_to_show + ' more error' + (more_errors_to_show > 1 ? 's' : '')).attr('class', 'total_errors');
            div.append('span').attr('class', 'show_all_errors').text('Show all').on('click', function () {
              d3.selectAll('.error.hidden').classed("hidden", false);
              d3.selectAll('.show_all_errors').classed("hidden", true);
              d3.selectAll('.total_errors').classed("hidden", true);
            });
          }

        }
      }
    }

    if (table_data.values.length > HEPDATA.default_row_limit) {
      d3.select("#table_options_region").append('span').text('Showing ' + HEPDATA.default_row_limit + ' of ' + table_data.values.length + ' values');
      var btn = d3.select("#table_options_region").append('a')
        .attr('class', 'btn-show-all-rows pull-right')
        .text('Show All ' + table_data.values.length + ' values');

      btn.on('click', function () {
        d3.select(this).classed('hidden', true);
        d3.select("#table_options_region span").text('Showing all ' + table_data.values.length + ' values');
        d3.selectAll('tr.data_values').classed('hidden', false);
        HEPDATA.table_renderer.filter_rows(HEPDATA.selected);
      })
    }
  },


  filter_rows: function (target_rows) {
    d3.selectAll("tr.data_values").classed('hidden', function () {
      var row_num = d3.select(this).attr('id').split("-")[1];
      return !(row_num in target_rows) && Object.keys(target_rows).length > 0;
    });
  }
};
