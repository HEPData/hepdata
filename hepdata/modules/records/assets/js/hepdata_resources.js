import $ from 'jquery'
import 'bootstrap'
import d3 from 'd3'
import HEPDATA from './hepdata_common.js'

HEPDATA.hepdata_resources = (function () {
  var ALL_RESOURCES = 'Common Resources';
  var resources = {};
  var initial_resource = ALL_RESOURCES;

  var show_resource = function (selected_item) {

    var _selected_item_resources = resources[selected_item];

    var placement = d3.select("#resource-list");
    placement.html("");

    d3.select('#add-resource-form')
      .attr('action', '/record/add_resource/'
        + _selected_item_resources.type + '/'
        + _selected_item_resources.id + '/'
        + _selected_item_resources.version);

    d3.select("#selected_resource_item").text(selected_item);

    var resource_item_container = placement.selectAll(".resource-item-container").data(_selected_item_resources.resources).enter().append("div").attr("class", "col-md-6 resource-item-container");

    var resource_item = resource_item_container.append("div").attr("class", "resource-item");

    resource_item.append("div").html(function (d) {
      if ('preview_location' in d) {
        d.file_type = 'image';
        return '<img src="' + d.preview_location + '" width="110px"/>';
      } else {
        return '<i class="fa fa-' + HEPDATA.map_file_type_to_property(d.file_type, 'icon') + '"></i>';
      }
    });

    resource_item.append("h4").text(function (d) {
      return HEPDATA.map_file_type_to_property(d.file_type, 'description');
    });

    resource_item.append("p").text(function (d) {
      return d['file_description'];
    });

    // Manage rendering of the data license value
    // Uses url, description and name from data_licence for anchor url, title, and text respectively
    resource_item.append("a")
      .attr('href', function(d) {
        return d['data_license'] ? d['data_license'].url : null;
      })
      .attr('title', function(d) {
        return d['data_license'] ? d['data_license'].description : null;
      })
      .text(function(d) {
        return d['data_license'] ? d['data_license'].name : null;
      });

    resource_item.append("p")
      .attr('display', function(d){
        return d['doi'] == null ? 'none' : 'block';
      }).html(function (d) {
        return d['doi'] == null ? '' : '<a href="https://doi.org/' + d['doi'] + '" class="resource-doi">' + d['doi'] + '</a>';
      });

    resource_item.append("a")
      .attr('target', '_new')
      .attr("class", "btn btn-primary btn-sm")
      .attr("href", function (d) {
        var download_location = d.location;
        if (d.location.indexOf('http') == -1) {
          download_location = '/record/resource/' + d.id + '?view=true';
        }
        return download_location;
      }).text(function (d) {
      if (d.location.indexOf('http') == -1) {
        return "Download"
      }
      return "View Resource";
    });

    HEPDATA.typeset([d3.select("#resourceModal").node()]);
  };

  var create_modal_view = function (recid, version) {
    $("#resourceModal").modal();
    $.ajax({
      type: 'GET',
      dataType: 'json',
      url: '/record/resources/' + recid + '/' + version,
      success: function (data) {



        var resource_list = d3.select("#resource-filter ul");
        resource_list.html('');

        data.submission_items.forEach(function(item) {
          resources[item.name] = item;
          var _li = resource_list.append('li')
            .attr('data-name', item.name)
            .attr('class', function () {
              return (initial_resource === item.name ? 'active' : '');
            });
          _li.text(item.name);
          _li.append('span').attr('class', 'badge pull-right').text(item.resources.length);
        });

        show_resource(initial_resource);
      }
    });

    $(document).on('click', '#resource-filter ul li', function () {
      var name = $(this).attr('data-name');
      $("#resource-filter ul li").each(function () {
        $(this).removeClass("active");
      });

      $(this).addClass("active");
      show_resource(name);
    })
  };

  var update_action = function () {
      var _analysis_type = $('#analysisType').val();
      var _analysis_other = $('#analysisOther').val();
      var _analysis_url = $('#analysisURL').val();

      $("#other_container").toggleClass('hidden', _analysis_type !== 'other');

      var _enable_button = ((_analysis_type !== 'other' || (_analysis_type === 'other' && _analysis_other !== ''))
      && _analysis_url != '');

      $("#addAnalysisBtn").prop('disabled', !_enable_button);
  };

  return {
    initialise: function (recid, version) {

      $(document).on('click', '#show_all_resources', function () {
        initial_resource = ALL_RESOURCES;
        create_modal_view(recid, version);
      });

      $(document).on('click', '#show_resources', function () {
        initial_resource = HEPDATA.current_table_name || ALL_RESOURCES;
        create_modal_view(recid, version);
      });

      $(".form-control").on('change', update_action);
      $(".form-control").on('keyup', update_action);

    },

    set_initial_resource: function (name) {
      initial_resource = name;
    }
  }

})
();
