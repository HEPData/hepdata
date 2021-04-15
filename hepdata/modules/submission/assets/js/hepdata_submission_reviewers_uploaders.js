import $ from 'jquery'

$(document).ready(function () {
  function isEmail(email) {
      var regex = /^([a-zA-Z0-9_.'+-])+\@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
      return regex.test(email);
  }

  $(".reviewer-uploader").on('input', function () {
      var all_valid = true;
      $(".reviewer-uploader").each(function () {
          if ($(this).val().length == 0) {
              all_valid = false;
          } else {
              if ($(this).attr('type') === 'email') {
                  if (!isEmail($(this).val())) {
                      all_valid = false;
                      $(this).addClass("with-error")
                  } else {
                      $(this).removeClass("with-error")
                  }
              }
          }
      });

      if (all_valid) {
          $("#people_continue_btn").prop("disabled", false)
      } else {
          $("#people_continue_btn").prop("disabled", true)
      }
  })
});
