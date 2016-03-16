HEPDATA.visualization = {};

HEPDATA.visualization.utils = {

  round: function (value, round) {
    try {
      value = value.toFixed(round)
    } catch (e) {
      console.warn('Unable to convert ' + value + ' to number.');
    }

    return value;
  },

  calculate_x_scale: function (scale_type, min, max, options, data) {

    var x_extent = d3.extent(data, function (d) {
      return d.x;
    });


    if (min == null) {
      //we only get null when the values are not numeric, so in this case we create an ordinal scale
      return d3.scale.ordinal().domain(data.map(function (d) {
        return d.x;
      })).rangePoints([0, options.width - options.margins.left - options.margins.right]);
    } else {
      var scale = scale_type == 'log' && HEPDATA.stats.min_x > 0 ? d3.scale.log() : d3.scale.linear();

      var range = [0, options.width - options.margins.left - options.margins.right];
      if (x_extent[0] == x_extent[1]) {
        var mid_way = (options.width - options.margins.left - options.margins.right) / 2;
        range = [mid_way, mid_way];
      }
      return scale.domain([min, max]).range(range);
    }
  },

  calculate_y_scale: function (scale_type, min, max, options) {
    var scale = scale_type == 'log' && HEPDATA.stats.min_y > 0 ? d3.scale.log() : d3.scale.linear();
    return scale.domain([min, max]).range([options.height - options.margins.top - options.margins.bottom, 0]);
  }
};



HEPDATA.dataprocessing = {
  /**
   * The data values come in a format relevant for tables, but not so good for use with D3.
   * We need to flatten things out in to objects representing each X,Y pair for display
   * @param data_values
   */
  process_data_values: function (data) {
    var processed_values = [];
    var toignore = [];
    var all_errors = [];
    var all_quad_errors = [];
    var groups = {};

    var group_types = {};
    for (var qualifier_key in data.qualifiers) {
      var qualifiers_record = data.qualifiers[qualifier_key];
      for (var qualifier_value_idx in qualifiers_record) {
        var qualifier_record = qualifiers_record[qualifier_value_idx];
        if (!(qualifier_record.group in groups)) {
          groups[qualifier_record.group] = [];
        }
        groups[qualifier_record.group].push(qualifier_record);

        if (!(qualifier_record.type in group_types)) {
          group_types[qualifier_record.type] = {
            "set": new Set(),
            "values": []
          };
        }

        group_types[qualifier_record.type]["set"].add(qualifier_record.value);
        group_types[qualifier_record.type]["values"].push(qualifier_record.value);
      }
    }

    var best_key = undefined;
    var headers = data.headers;

    var expanded_headers = [];
    for (var header_obj in headers) {
      for (var i = 0; i < headers[header_obj].colspan; i++) {
        expanded_headers.push(headers[header_obj])
      }
    }

    for (var key in group_types) {
      if (group_types[key]["set"].size == (expanded_headers.length - 1)) {
        best_key = key;
      }
    }


    for (var data_record in data.values) {
      var record = data.values[data_record];
      for (var y_idx in record.y) {
        if (record.y[y_idx].value != null) {
          var processed_value = {};
          if (expanded_headers[+y_idx + 1]) {
            var data_header_value = expanded_headers[+y_idx + 1].name;

            if (group_types[best_key]) {
              data_header_value += "::" + best_key + ":" + group_types[best_key]["values"][y_idx] + "::" + y_idx;
            }

            if (record.x.length > 1) {

              var x1_idx = 0, x2_idx = 1;
              for (var idx = 0; idx < HEPDATA.visualization.heatmap.data.headers.length; idx++) {
                if (HEPDATA.visualization.heatmap.data.headers[idx].name == HEPDATA.visualization.heatmap.x_index) {
                  x1_idx = idx;
                }
                if (HEPDATA.visualization.heatmap.data.headers[idx].name == HEPDATA.visualization.heatmap.y_index) {
                  x2_idx = idx;
                }
              }
              processed_value = {

                "x": record.x[x1_idx],
                "y": record.x[x2_idx],
                "value": record.y[y_idx].value,
                "name": data_header_value,
                "row": data_record
              };

              if (isNaN(processed_value.value)) continue;

              if (processed_value.value < HEPDATA.stats.min_value) HEPDATA.stats.min_value = processed_value.value;
              if (processed_value.value > HEPDATA.stats.max_value) HEPDATA.stats.max_value = processed_value.value;

            } else {
              processed_value = {
                "x": record.x[0],
                "y": record.y[y_idx].value,
                "name": data_header_value,
                "row": data_record
              };

              if (processed_value.y == '-') continue;
            }

            processed_value = HEPDATA.dataprocessing.processed_key(processed_value, 'x');
            processed_value = HEPDATA.dataprocessing.processed_key(processed_value, 'y');

            var errors = [];

            var summed_uncertainties = {"up": 0, "down": 0};

            if (record.x.length == 1) {
              for (var error_idx in record.y[y_idx].errors) {

                var errors_obj = $.extend(record.y[y_idx].errors[error_idx], {});
                errors_obj.x = processed_value.x;
                errors_obj.y = record.y[y_idx].value;
                errors_obj.group = record.y[y_idx].group;
                errors_obj.name = data_header_value;

                if ("asymerror" in errors_obj) {
                  var up_err = HEPDATA.dataprocessing.process_error_value(errors_obj['asymerror']['plus'], errors_obj.y);
                  var down_err = HEPDATA.dataprocessing.process_error_value(errors_obj['asymerror']['minus'], errors_obj.y);
                  errors_obj.err_plus = Math.max(down_err, up_err, 0);
                  errors_obj.err_minus = Math.min(down_err, up_err, 0);

                } else if ("symerror" in errors_obj) {
                  //we have a symerror
                  var value = HEPDATA.dataprocessing.process_error_value(errors_obj['symerror'], errors_obj.y);
                  errors_obj.err_plus = value;
                  errors_obj.err_minus = value == 0 ? 0 : -value;
                }

                if (errors_obj.y + errors_obj.err_plus > HEPDATA.stats.max_y) HEPDATA.stats.max_y = errors_obj.err_plus + errors_obj.y;
                if (errors_obj.y + errors_obj.err_minus < HEPDATA.stats.min_y) HEPDATA.stats.min_y = errors_obj.err_minus + errors_obj.y;

                summed_uncertainties["up"] += Math.pow(errors_obj.err_plus, 2);
                summed_uncertainties["down"] += Math.pow(errors_obj.err_minus, 2);

                errors.push(errors_obj);
                all_errors.push(errors_obj);
              }


              processed_value["quad_error"] = {
                x: processed_value.x,
                y: record.y[y_idx].value,
                'err_plus': Math.sqrt(summed_uncertainties["up"]),
                'err_minus': -Math.sqrt(summed_uncertainties["down"]),
                'label': 'Summed',
                'name': data_header_value
              };

              if (summed_uncertainties["up"] == 0 && summed_uncertainties["down"] == 0) {
                processed_value["quad_error"]["label"] = "hidden";
              }

              all_quad_errors.push(processed_value["quad_error"]);

              processed_value["errors"] = errors;
              processed_value["group"] = record.y[y_idx].group;
            }

            processed_values.push(processed_value);
          }
        } else {
          toignore.push(record.x);
        }
      }
    }


    return {
      "processed": processed_values,
      "ignore": toignore,
      "errors": all_errors,
      "quad_error": all_quad_errors,
      "groups": groups
    };
  },

  process_error_value: function (error_value, value) {
    //we need to check if percentage values etc.
    if (isNaN(error_value) && error_value.indexOf('%') != -1) {
      //we have a percentage, deal with this
      error_value = parseFloat(error_value.replace("%", ""));
      error_value = (value / 100) * error_value;

      return error_value;
    } else {
      return parseFloat(error_value);
    }
  },

  /**
   * Processes X ranges specified as 0.1 - 0.4 in to the start range, end range, and mid value.
   * @param processed_value_obj
   * @param key - e.g. x or y to be processed
   */
  processed_key: function (processed_value_obj, key) {
    var val = processed_value_obj[key];

    if (val != undefined) {
      if (!isNaN(parseFloat(val["high"])) && !isNaN(parseFloat(val["low"]))) {
        var value = val["value"];
        try {
          value = parseFloat(val["value"])
        } catch (e) {
          console.error(e)
        }

        var high = parseFloat(val["high"]);
        var low = parseFloat(val["low"]);

        high = Math.max(low, high);
        low = Math.min(low, high);

        if (!isNaN(value)) {
          processed_value_obj[key + '_max'] = high;
          processed_value_obj[key + '_min'] = low;
          processed_value_obj[key] = value;
        } else {
          processed_value_obj[key + '_min'] = low;
          processed_value_obj[key + '_max'] = high;
          processed_value_obj[key] = high - ((high - low) / 2);
        }

        if (processed_value_obj[key + '_max'] > HEPDATA.stats['max_' + key])  HEPDATA.stats['max_' + key] = processed_value_obj[key + '_max'];
        if (processed_value_obj[key + '_min'] < HEPDATA.stats['min_' + key])  HEPDATA.stats['min_' + key] = processed_value_obj[key + '_min'];
      } else if (typeof(val["value"]) == 'string' && val["value"].split('-').length > 1) {
        var low_high = val["value"].split('-');

        if (!isNaN(low_high[1]) && !isNaN(low_high[0])) {
          processed_value_obj[key + '_max'] = +low_high[1];
          processed_value_obj[key + '_min'] = +low_high[0];
          processed_value_obj[key] = +processed_value_obj[key + '_min'] + ((processed_value_obj[key + '_max'] - processed_value_obj[key + '_min']) / 2);
        }

        if (processed_value_obj[key + '_max'] > HEPDATA.stats['max_' + key])  HEPDATA.stats['max_' + key] = processed_value_obj[key + '_max'];
        if (processed_value_obj[key + '_min'] < HEPDATA.stats['min_' + key])  HEPDATA.stats['min_' + key] = processed_value_obj[key + '_min'];

      } else if (!isNaN(parseFloat(val["value"]))) {
        processed_value_obj[key] = +val["value"];

        if (processed_value_obj[key] > HEPDATA.stats['max_' + key])  HEPDATA.stats['max_' + key] = processed_value_obj[key];
        if (processed_value_obj[key] < HEPDATA.stats['min_' + key])  HEPDATA.stats['min_' + key] = processed_value_obj[key];

      } else {
        if (key == 'x') {
          processed_value_obj[key] = val["value"];
          HEPDATA.stats['max_' + key] = null;
          HEPDATA.stats['min_' + key] = null;
        }
      }
    }
    return processed_value_obj;
  },


  /**
   * Removes non-alpha characters from the start of a string string, and non-alphanum characters
   * from the rest of the string.
   * @param string
   */
  cleanup_string: function (string) {
    if (string) {
      //remove numbers from the beginning of the string..
      if (isNaN(string)) {
        string = HEPDATA.dataprocessing.convert_number_to_string(string);
      }
      string = string.replace(/^[[\-|\+]*[0-9\*\s]+/gi, "");
      return string.replace(/[^a-zA-Z0-9]+/gi, "");
    } else {
      return '';
    }
  },

  /**
   * In the event where a string is just a number, we need to get an alpha representation
   * @param string
   */
  convert_number_to_string: function (string) {
    var converted = '';
    for (var a in string) {
      if (isNaN(string[a])) {
        converted += string[a]
      } else {
        converted += String.fromCharCode(97 + parseInt(string[a]))
      }
    }
    return converted;
  }
};

HEPDATA.legends = {

  draw_error_legend: function (legend_placement, all_variables, options) {
    d3.select(legend_placement).html('');

    var rendering_options = d3.select(legend_placement).append("div").attr("class", "options");
    HEPDATA.visualization.histogram.render_option("Sum errors", 'bool', "draw_summed_error", rendering_options, "HEPDATA.visualization.histogram.toggle_bool_option('draw_summed_error', this)");

    if (HEPDATA.visualization.histogram.histogram_added) {
      HEPDATA.visualization.histogram.render_option("Fill bars", 'bool', "fill_bars", rendering_options, "HEPDATA.visualization.histogram.toggle_bool_option('fill_bars', this)");
    }

    if (HEPDATA.stats.min_x > 0) HEPDATA.visualization.histogram.render_option("Log Scale (X)", 'scale', "x_scale", rendering_options, "HEPDATA.visualization.histogram.toggle_scale_option('x_scale', this)");
    if (HEPDATA.stats.min_y > 0) HEPDATA.visualization.histogram.render_option("Log Scale (Y)", 'scale', "y_scale", rendering_options, "HEPDATA.visualization.histogram.toggle_scale_option('y_scale', this)");

    rendering_options.append("hr");
    d3.select(legend_placement).append("div").attr("class", "legend-info").text("Deselect variables or hide different error bars by clicking on them.");

    var table = d3.select(legend_placement).append("table").attr("class", "legend-table").style("table-layout", "fixed");

    var thead = table.append("thead").append("tr");
    thead.append("td").attr('style', 'padding-top:10px').text("Variables");

    var tbody = table.append("tbody");

    var variables = {};
    all_variables.map(function (d) {

      d.label = d.label == "" ? HEPDATA.default_error_label : d.label;
      if (!(d.name in variables)) {
        variables[d.name] = [];
      }

      if (!d.hide) {
        if (variables[d.name].indexOf(d.label) == -1) {
          variables[d.name].push(d.label);
        }
      }
    });

    for (var variable_name in variables) {

      var cleaned_var_name = HEPDATA.dataprocessing.cleanup_string(variable_name);
      var variable_parts = variable_name.split("::");

      var tr = tbody.append("tr");
      var td = tr.append("td").text(variable_parts[0]).attr("id", cleaned_var_name)
        .attr("class", "error-legend-item variable-name").style("color", options.colors(variable_name)).style("border-bottom", options.colors(variable_name));

      td.append('div').attr('class', 'error-qualifier-info').text(variable_parts[1]);

      var errors = variables[variable_name];

      for (var error in errors) {
        var error_value = errors[error] == undefined ? HEPDATA.default_error_label : errors[error];
        if (error_value != "hidden") {
          var tr = tbody.append("tr");
          tr.append("td").text(error_value + " error").attr("class", function () {
              return "variable-error error-legend-item error-" + cleaned_var_name;
            })
            .attr("id", cleaned_var_name + "-error-" + HEPDATA.dataprocessing.cleanup_string(error_value)
            )
        }
      }
      tbody.append("div").attr("class", "clearfix");
    }

    $(".error-legend-item").bind('click', function () {
      var item_id = this.id;
      // we need to have logic in place for the variable display and error display
      d3.selectAll("." + this.id).transition().duration(100).style("opacity", function () {
        var this_opacity = d3.select(this).style("opacity");
        var overall_opacity = this_opacity == 1 ? 0.4 : 1;

        d3.select("#" + item_id).transition().duration(100).style("opacity", overall_opacity);
        if (overall_opacity < 0.5) {
          d3.selectAll(".ebar-" + item_id).transition().duration(100).style("opacity", 0);
          d3.selectAll(".error-" + item_id).transition().duration(100).style("opacity", 0.4);
        } else {
          d3.selectAll(".ebar-" + item_id).transition().duration(100).style("opacity", 1);
          d3.selectAll(".error-" + item_id).transition().duration(100).style("opacity", 1);
        }
        return overall_opacity < 0.5 ? 0 : 1;

      });
    });

    MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
  }

};
