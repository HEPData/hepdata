import $ from 'jquery'
import ClipboardJS from 'clipboard'
import HEPDATA from './hepdata_common.js'

HEPDATA.hepdata_record = (function () {

    var preserve_abstract_line_wrap = function () {
      var abstract_html = $(".record-abstract-content").html();
      if (abstract_html) $(".record-abstract-content").html(abstract_html.trim());
    };

    var initialise_clipboard = function (selector) {
      new ClipboardJS(selector);
    };

    return {
      initialise: function () {
        preserve_abstract_line_wrap();
        initialise_clipboard('.copy-btn');
      },

      perform_upload_action: function (event, placement, form_name, colors, insertion_type) {
        if (event) {
          event.preventDefault();
        }

        var form = document.forms[form_name];
        var upload_size = $('input[name="hep_archive"]')[0].files[0].size;
        if (upload_size > HEPDATA.upload_max_size) {
          var message = '<p>Your submission of size ' + Math.round(upload_size/1024/1024) + ' MB is too large to be uploaded.</p>';
          message += '<p>Please reduce the size of your upload file to less than ' + Math.round(HEPDATA.upload_max_size/1024/1024) + ' MB and try again.</p>';
          message += '<p>Please contact info@hepdata.net if you need any further information.</p>';
          message += '<p><a href="" onclick="window.location.reload(false);">Try again</a></p>';
          var html = '<div id="upload-message">' + message + '</div>';
          $(".upload-form").css('display', 'none');
          $(placement).append(html);
          return;
        }

        var message = '<p>Uploading file...</p>'
        message += '<p>(Timeout after ' + Math.round(HEPDATA.upload_timeout/60) + ' minutes.)</p>';
        var html = '<div id="upload-progress"></div>' +
          '<div id="upload-message">' + message + '</div>';
        if (insertion_type === 'large_area') {
          html = '<div id="upload-progress"></div>' +
            '<div style="width: 300px; margin: 0 auto;" id="upload-message"><p>' + message + '</p></div>';
        }

        $(".upload-form").css('display', 'none');

        $(placement).append(html);

        if (colors === undefined) {
          colors = ["#955BA5", "white"]
        }

        HEPDATA.render_loader("#upload-progress", [
            {x: 26, y: 30, color: colors[0]},
            {x: -60, y: 55, color: colors[1]},
            {x: 37, y: -10, color: colors[0]},
            {x: -60, y: 10, color: colors[0]},
            {x: -27, y: -30, color: colors[0]},
            {x: 60, y: -55, color: colors[1]}],
          {"width": 200, "height": 200}
        );

        var data = new FormData(form);

		    $.ajax({
            type: "POST",
            enctype: 'multipart/form-data',
            url: form.action,
            data: data,
            dataType: "text json",
            processData: false,
            contentType: false,
            cache: false,
            timeout: HEPDATA.upload_timeout * 1000,
            success: function (data) {
              window.location.href = data['url'];
            },
            error: function (e, statusCode, text) {
              message = "<p>We were unable to upload your file.</p>";

              if (e.statusText == "timeout") {
                message += "<p>Your submission was too large to be uploaded within the timeout limit of " + Math.round(HEPDATA.upload_timeout/60)+ " minutes.</p>";
                message += "<p>Please reduce the size of your upload file and try again.</p>";
                message += "<p>Please contact info@hepdata.net if you need any further information.</p>";
              } else if (e.responseJSON && e.responseJSON['message']) {
                message += "<p>" + e.responseJSON['message'] + "</p>";
              } else {
                message += "<p>An unexpected error occurred. Please try again later, or contact info@hepdata.net if the message persists.</p>";
                message += "<p>Error details: " + e.status + " " + text + "</p>";
              }

              message += '<p><a href="" onclick="window.location.reload(false);">Try again</a></p>'

              $('#upload-progress').remove();
              $('#upload-message').html(message)
            }
        });

      },

      load_revise_submission: function() {
        $.ajax({
            dataType: "json",
            url: '/record/coordinator/view/' + HEPDATA.current_record_id,
            processData: false,
            cache: true,
            success: function (data) {
              function create_section_contents(placement, array, type, additional_class) {
                  // reset html
                  $(placement).html('');
                  if (array.length > 0) {
                      for (var val_idx in array) {
                          var html_block = '<div class="' + type + ' ' + additional_class + '">';
                          html_block += '<div class="info">' + array[val_idx]['full_name'] + '<br/><span class="review-email">' + array[val_idx]['email'] + '</span></div>';
                          html_block += '<div class="clearfix"></div>';

                          $(placement).append(html_block)
                      }
                  } else {
                      $(placement).html('<p class="no-entries">No ' + additional_class + ' ' + type + '</p>');
                  }
              }

              create_section_contents("#primary-reviewer", data['primary-reviewers'], 'reviewer', 'primary');
              create_section_contents("#primary-uploader", data['primary-uploaders'], 'uploader', 'primary');
              create_section_contents("#reserve-reviewer", data['reserve-reviewers'], 'reviewer', 'reserve');
              create_section_contents("#reserve-uploader", data['reserve-uploaders'], 'uploader', 'reserve');
              if (data['primary-uploaders'].length > 0) {
                $("#notify-uploader-name").text('(' + data['primary-uploaders'][0]['full_name'] + ')')
              }
            }
        });
      },

      revise_submission: function(redirect_url) {
        var form = document.forms['notify-uploader-form'];
        var data = $(form).serialize();

        $("#revise-submission-container .col-md-12").html('<div align="center"/>');
        HEPDATA.render_loader(
          "#revise-submission-container .col-md-12 div",
          [
            {x: 26, y: 30, color: "#955BA5"},
            {x: -60, y: 55, color: "#2C3E50"},
            {x: 37, y: -10, color: "#955BA5"},
            {x: -60, y: 10, color: "#955BA5"},
            {x: -27, y: -30, color: "#955BA5"},
            {x: 60, y: -55, color: "#2C3E50"}
          ],
          {"width": 100, "height": 100}
        );
        $("#revise-submission-container .col-md-12 div").append("<p>Creating new version...</p>");

        $.ajax({
            type: "POST",
            url: "/record/" + HEPDATA.current_record_id + "/revise-submission",
            data: data,
            cache: false,
            success: function (data) {
              if (data.success) {
                $("#new-version-number").html(data.version);
                $("#revise-confirm").hide();
                $("#revise-success").removeClass('hidden');

                var count = 5;
                setInterval(function () {
                  count -= 1;
                  $("#revise-timer").text(count);
                  if (count == 0) {
                    $("#reviseSubmission").modal('hide');
                  }
                }, 1000);
                setTimeout(function () {
                  window.location = redirect_url;
                }, 5500);
              } else {
                var closeButtonHtml = '<button type="button" class="btn btn-info" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">Close</span></button>';
                $("#revise-submission-container .col-md-12").append('<p>Failed. Please try again later.</p>' + closeButtonHtml);
              }
            }
          }
        );
      }
    }
  }
)();
