HEPDATA.visualization.histogram = {

  brush: undefined,
  x_axis: undefined,
  y_axis: undefined,
  x_scale: undefined,
  y_scale: undefined,
  data: undefined,
  histogram_added: false,
  x_index: '',
  placement: undefined,
  modes: {"scatter": "SCATTER_ONLY", "hist": "HISTOGRAM"},
  options: {
    brushable: true,
    legend_groups: true,
    fill_bars: false,
    draw_summed_error: true,
    animation_duration: 100,
    error_line_width: 0.3,
    margins: {"left": 40, "right": 30, "top": 10, "bottom": 30},
    colors: d3.scale.ordinal().range(["#2C3E50", "#8E44AD", "#27AE60", "#3498DB", "#D35400", "#7F8C8D"]),
    height: 400,
    width: 400,
    mode: "histogram",
    dashed: ["GGM 700 200 1.5"],
    y_scale: 'linear', // can be lin (linear) or log
    x_scale: 'linear' // can be lin (linear) or log
  },

  render: function (data, placement, options) {
    $(placement).html('');

    HEPDATA.visualization.histogram.data = data;
    HEPDATA.visualization.histogram.placement = placement;
    HEPDATA.visualization.histogram.histogram_added = false;
    HEPDATA.reset_stats();

    HEPDATA.visualization.histogram.options = $.extend(HEPDATA.visualization.histogram.options, options);

    var processed_dict = HEPDATA.dataprocessing.process_data_values(data, HEPDATA.visualization.histogram.options);

    if ((data.headers[0] == undefined || data.headers[0].name == '') && data.values.length == 0) {
      d3.select(placement).append("div").attr("class", "alert alert-warning").text("Unable to render a plot since there is no data to render.");
      d3.select("#legend").html('');
      return
    }

    HEPDATA.visualization.histogram.x_index = data.headers[0].name;

    HEPDATA.visualization.histogram.x_scale = HEPDATA.visualization.utils.calculate_x_scale(HEPDATA.visualization.histogram.options.x_scale, HEPDATA.stats.min_x, HEPDATA.stats.max_x, HEPDATA.visualization.histogram.options, processed_dict["processed"]);
    HEPDATA.visualization.histogram.y_scale = HEPDATA.visualization.utils.calculate_y_scale(HEPDATA.visualization.histogram.options.y_scale, HEPDATA.stats.min_y, HEPDATA.stats.max_y, HEPDATA.visualization.histogram.options, processed_dict["processed"]);

    HEPDATA.visualization.histogram.x_axis = d3.svg.axis().scale(HEPDATA.visualization.histogram.x_scale).orient("bottom").tickPadding(2);
    HEPDATA.visualization.histogram.y_axis = d3.svg.axis().scale(HEPDATA.visualization.histogram.y_scale).orient("left").tickPadding(2);

    var svg = d3.select(placement).append("svg").attr("width", HEPDATA.visualization.histogram.options.width).attr("height", HEPDATA.visualization.histogram.options.height).attr("preserveAspectRatio", "xMinYMin meet")
      //class to make it responsive
      .classed("svg-content-responsive", true).append("g")
      .attr("transform", "translate(" + HEPDATA.visualization.histogram.options.margins.left + "," + HEPDATA.visualization.histogram.options.margins.top + ")").append("g").attr("class", "plot");

    // we look through the values and create a dictionary mapping a variable to an array of data sorted by the x value.
    // this can then be used to create the lines.
    var _aggregated_values = {};

    for (var value_idx in processed_dict["processed"]) {
      var value_obj = processed_dict["processed"][value_idx];

      if (!(value_obj.name in _aggregated_values )) {
        _aggregated_values[value_obj.name] = {
          "name": value_obj.name,
          "values": [],
          "x_error": "x_min" in value_obj,
          "y_errors": value_obj.errors[0] ? !value_obj.errors[0].hide : false
        };
      }


      if (_aggregated_values[value_obj.name]["y_errors"]) {
        _aggregated_values[value_obj.name]["values"].push(value_obj);
      } else if (HEPDATA.visualization.histogram.options.mode != HEPDATA.visualization.histogram.modes.scatter &&
                 value_obj.x_min != undefined &&
                 (HEPDATA.visualization.histogram.options.x_scale != 'log' || value_obj.x_min > 0)) {
        _aggregated_values[value_obj.name]["values"].push({
          x: value_obj.x_min,
          y: value_obj.y,
          errors: value_obj.errors
        });
        _aggregated_values[value_obj.name]["values"].push({
          x: value_obj.x_max,
          y: value_obj.y,
          errors: value_obj.errors
        });
      } else {
        _aggregated_values[value_obj.name]["values"].push(value_obj);
      }
    }

    var line = d3.svg.line()
      .interpolate("linear")
      .x(function (d) {
        return HEPDATA.visualization.histogram.x_scale(d.x);
      })
      .y(function (d) {
        return HEPDATA.visualization.histogram.y_scale(d.y);
      });


    var keys = Object.keys(_aggregated_values);
    for (var i = keys.length - 1; i >= 0; i--) {

      var value = keys[i];

      if (_aggregated_values[value]["y_errors"] || value_obj.x_min == undefined) {
        HEPDATA.visualization.histogram.create_scatter_plot(svg, _aggregated_values[value].values,
          _aggregated_values[value]["x_error"],
          _aggregated_values[value]["y_errors"], "histogram", value);
      } else {
        var node = svg.selectAll("g.hist").append('g')
          .data([_aggregated_values[value]]);

        var path = node.enter().append("path")
          .attr("class", function (d) {
            return "hist " + HEPDATA.dataprocessing.cleanup_string(d.name)
          })
          .attr("d", function (d, i) {
            if (HEPDATA.visualization.histogram.options.fill_bars) {
              d.values.unshift({
                x: HEPDATA.stats.min_x,
                y: HEPDATA.stats.min_y
              });
            }
            d.values.push({
              x: HEPDATA.stats.max_x,
              y: HEPDATA.stats.min_y
            });
            var line_path = d.values;
            return line(line_path) + (HEPDATA.visualization.histogram.options.fill_bars ? "z" : "");
          })
          .attr("stroke", function (d) {
            return HEPDATA.visualization.histogram.options.colors(d.name);
          })
          .attr("stroke-dasharray", function (d) {
            if (HEPDATA.visualization.histogram.options.dashed.indexOf(d.name) != -1) {
              return HEPDATA.visualization.histogram.options.width * .009 + ", " + HEPDATA.visualization.histogram.options.width * .015;
            }
          })
          .attr("stroke-width", HEPDATA.visualization.histogram.options.width * .01)
          .attr("fill", function (d) {
            return HEPDATA.visualization.histogram.options.fill_bars ? HEPDATA.visualization.histogram.options.colors(d.name) : "none";
          })
          .attr('opacity', HEPDATA.visualization.histogram.options.fill_bars ? 0.7 : 1)
          .attr("stroke-linecap", "round");

        HEPDATA.visualization.histogram.histogram_added = true;
      }
    }

    var find = '\\$';
    var re_matheq = new RegExp(find, 'g');

    HEPDATA.visualization.histogram.x_index = HEPDATA.visualization.histogram.x_index.replace(re_matheq, '');

    svg.append("g").attr("class", "x axis")
      .attr("transform", "translate(0," + (HEPDATA.visualization.histogram.options.height - HEPDATA.visualization.histogram.options.margins.bottom - HEPDATA.visualization.histogram.options.margins.top) + ")")
      .call(HEPDATA.visualization.histogram.x_axis);
    svg.append("text")
      .attr("class", "axis_text")
      .attr("text-anchor", "middle")
      .attr("width", HEPDATA.visualization.histogram.options.width).attr("height", 25)
      .attr("x", HEPDATA.visualization.histogram.options.width / 3)
      .attr("y", HEPDATA.visualization.histogram.options.height - 10)
      .text(HEPDATA.visualization.histogram.x_index);

    if (HEPDATA.visualization.histogram.options.y_scale == "linear" && HEPDATA.stats.max_y > 1e5) {
      svg.append("g").attr("class", "y axis").call(HEPDATA.visualization.histogram.y_axis.tickFormat(d3.format(".1e"))).attr("transform", "translate(-4,0)");
    } else {
      svg.append("g").attr("class", "y axis").call(HEPDATA.visualization.histogram.y_axis).attr("transform", "translate(-4,0)");
    }

    HEPDATA.legends.draw_error_legend("#legend", HEPDATA.visualization.histogram.options.draw_summed_error ? processed_dict["quad_error"] : processed_dict["errors"], HEPDATA.visualization.histogram.options);

    if (HEPDATA.visualization.histogram.options.brushable) {
      HEPDATA.visualization.histogram.brush = d3.svg.brush()
        .x(HEPDATA.visualization.histogram.x_scale)
        .y(HEPDATA.visualization.histogram.y_scale)
        .on("brushstart", function () {
          HEPDATA.selected = {};
        })
        .on("brush", HEPDATA.visualization.histogram.brushed)
        .on("brushend", function () {
          HEPDATA.table_renderer.filter_rows(HEPDATA.selected);
        });

      svg.append("g")
        .attr("class", "brush")
        .call(HEPDATA.visualization.histogram.brush);
    }
  },

  render_option: function (text, type, option, parent_node, function_call) {
    var div = parent_node.append("div").attr("style", "display: inline-block;padding:3px");
    div.append("label").text(text).attr("style", "padding:3px");
    var checkbox = div.append("input")
      .attr("type", "checkbox")
      .attr("onClick", function_call);

    if (type == 'bool') {
      if (HEPDATA.visualization.histogram.options[option]) {
        checkbox.attr("checked", "checked")
      }
    } else if (type == 'scale')
      if (HEPDATA.visualization.histogram.options[option] == "log") {
        checkbox.attr("checked", "checked")
      }
  },


  toggle_scale_option: function (option, caller) {
    HEPDATA.visualization.histogram.options[option] = d3.select(caller).property("checked") ? "log" : "linear";
    HEPDATA.visualization.histogram.render(HEPDATA.visualization.histogram.data, HEPDATA.visualization.histogram.placement, {});
  },

  toggle_bool_option: function (option, caller) {
    HEPDATA.visualization.histogram.options[option] = d3.select(caller).property("checked");
    HEPDATA.visualization.histogram.render(HEPDATA.visualization.histogram.data, HEPDATA.visualization.histogram.placement, {});
  },


  brushed: function () {
    var extent = HEPDATA.visualization.histogram.brush.extent();
    HEPDATA.selected = {};

    d3.selectAll("g.node").select("circle").style("fill", function (d) {
      var x = d.x;
      var y = d.y;

      if (isNaN(d.x)) x = HEPDATA.visualization.histogram.x_scale(x);

      d.selected = (x >= (extent[0][0]) && x <= (extent[1][0])
      && (y >= extent[0][1]) && (y <= extent[1][1]));

      if (d.selected) HEPDATA.selected[d.row] = d;

      return d.selected ? "#F15D2F" : HEPDATA.visualization.histogram.options.colors(d.name);
    });

  },

  create_scatter_plot: function (svg, values, has_x_error, has_y_error, type, id) {
    var dot_groups = svg.selectAll("g.node " + HEPDATA.dataprocessing.cleanup_string(id)).append('g').attr("class", "node " + HEPDATA.dataprocessing.cleanup_string(id))
      .data(values);

    var dotGroup = dot_groups.enter().append("g").attr("class", function (d) {
      return "node " + HEPDATA.dataprocessing.cleanup_string(d.name);
    }).attr('id', function (d) {
      return 'row-' + d.row;
    }).attr('transform', function (d) {
      return "translate(" + (HEPDATA.visualization[type].x_scale(d.x)) + "," + HEPDATA.visualization[type].y_scale(d.y) + ")";
    });

    // draw x errors if they should be drawn :)
    if (has_x_error) {
      dot_groups.selectAll('rect.x_err').data(function (d) {
        return [d];
      }).enter()
        .append("rect")
        .attr("x", function (d) {
          if (d.x_min != undefined && HEPDATA.visualization[type].x_scale(d.x_min) != undefined) {
            return HEPDATA.visualization[type].x_scale(d.x_min) - HEPDATA.visualization[type].x_scale(d.x);
          } else {
            return 0;
          }
        })
        .attr("y", 0)
        .attr("width", function (d) {
          if (d.x_min != undefined && HEPDATA.visualization[type].x_scale(d.x_min) != undefined) {
            return HEPDATA.visualization[type].x_scale(d.x_max) - HEPDATA.visualization[type].x_scale(d.x_min);
          } else {
            return 0;
          }
        })
        .attr("height", 1)
        .style("stroke", "#2C3E50")
        .attr("class", function (d, i) {
          var variable = HEPDATA.dataprocessing.cleanup_string(d.name);
          return "x_err ebar-" + variable;
        })
    }

    if (has_y_error) {

      if (HEPDATA.visualization[type].options.draw_summed_error) {
        dot_groups.append("line")
          .attr("x1", 0)
          .attr("y1", function (d) {
            if (!isNaN(d.quad_error.err_minus) &&
                (HEPDATA.visualization[type].options.y_scale != 'log' || (d.y + d.quad_error.err_minus) > 0)) {
              return HEPDATA.visualization[type].y_scale(d.y + d.quad_error.err_minus) - HEPDATA.visualization[type].y_scale(d.y);
            } else {
              return 0;
            }
          })
          .attr("x2", 0)
          .attr("y2", function (d) {
            if (!isNaN(d.quad_error.err_plus) &&
                (HEPDATA.visualization[type].options.y_scale != 'log' || (d.y + d.quad_error.err_plus) > 0)) {
              return HEPDATA.visualization[type].y_scale(d.y + d.quad_error.err_plus) - HEPDATA.visualization[type].y_scale(d.y);
            } else {
              return 0;
            }
          })
          .attr("stroke-width", 2)
          .style("stroke", "#2C3E50")
          .attr("class", function (d, i) {
            var label = d.quad_error.label == undefined ? HEPDATA.default_error_label : d.quad_error.label;
            label = HEPDATA.dataprocessing.cleanup_string(label);
            var variable = HEPDATA.dataprocessing.cleanup_string(d.name);
            return "y_err line error-" + label + " " + variable + "-error-" + label + " ebar-" + variable;
          });
      }
      else {

        dot_groups.selectAll('rect.y_err').data(function (d) {
          return d.errors;
        }).enter()
          .append("line")
          .attr("x1", 0)
          .attr("y1", function (d) {
            if (!isNaN(d.err_minus)) {
              return HEPDATA.visualization[type].y_scale(d.y + d.err_minus) - HEPDATA.visualization[type].y_scale(d.y);
            } else {
              return 0;
            }
          })
          .attr("x2", 0)
          .attr("y2", function (d) {
            if (!isNaN(d.err_plus)) {
              return HEPDATA.visualization[type].y_scale(d.y + d.err_plus) - HEPDATA.visualization[type].y_scale(d.y);
            } else {
              return 0;
            }
          })

          .attr("stroke-width", 2)
          .style("stroke", "#2C3E50")
          .attr("class", function (d, i) {
            var label = d.label == undefined ? HEPDATA.default_error_label : d.label;
            label = HEPDATA.dataprocessing.cleanup_string(label);
            var variable = HEPDATA.dataprocessing.cleanup_string(d.name);
            return "y_err line error-" + label + " " + variable + "-error-" + label + " ebar-" + variable;
          });
      }
    }

    dotGroup.append("circle")
      .attr("r", 3)
      .attr("class", "dot")
      .style("fill", function (d) {
        return HEPDATA.visualization[type].options.colors(d.name);
      })
  }
};
